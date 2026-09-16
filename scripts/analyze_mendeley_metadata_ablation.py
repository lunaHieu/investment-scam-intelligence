"""Run a leakage-aware metadata ablation on the frozen Mendeley group split.

The experiment deliberately separates account/behaviour metadata from content
statistics and compares models with and without explicit missing-value flags.
Source identity is never a predictive feature. It is used only for diagnostics
and stratified evaluation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
from scipy import sparse
from scipy.stats import binomtest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler


RANDOM_STATE = 20260914
LABEL_SEMANTICS = (
    "Mendeley V2 source label: harmonized investment-related deceptive or suspicious "
    "content; not verified investment-scam ground truth for every record."
)

ACCOUNT_BEHAVIOUR_COLUMNS = (
    "followers",
    "friends_following",
    "statuses_posts",
    "account_age_days",
    "repost_count",
    "follower_following_ratio",
    "engagement_to_follower_ratio",
    "activity_burstiness",
    "verified_bool",
    "has_bio",
    "has_location",
    "has_url",
    "is_private",
    "default_profile_image_flag",
)
CONTENT_STATISTIC_COLUMNS = (
    "mention_count",
    "hashtag_count",
    "content_length",
    "word_count",
    "mention_intensity",
    "hashtag_loading",
)
ALL_METADATA_COLUMNS = ACCOUNT_BEHAVIOUR_COLUMNS + CONTENT_STATISTIC_COLUMNS
LOG1P_COLUMNS = {
    "followers",
    "friends_following",
    "statuses_posts",
    "account_age_days",
    "repost_count",
    "mention_count",
    "hashtag_count",
    "content_length",
    "word_count",
}
PROHIBITED_PREDICTIVE_FIELDS = {
    "record_id",
    "source_dataset",
    "source_modality",
    "has_metadata",
    "label",
    "partition",
    "gate_path",
    "investment_score",
    "lexicon_hits",
    "lexicon_score",
    "semantic_score",
    "original_partition",
    "split_group_id",
}


@dataclass(frozen=True)
class Variant:
    name: str
    use_text: bool
    metadata_space: str | None


VARIANTS = (
    Variant("text_only", True, None),
    Variant("account_behaviour_only_values", False, "account_values"),
    Variant("content_statistics_only_values", False, "content_values"),
    Variant("all_metadata_only_values", False, "all_values"),
    Variant("all_metadata_only_with_missingness", False, "all_with_missingness"),
    Variant("text_plus_account_behaviour_values", True, "account_values"),
    Variant("text_plus_content_statistics_values", True, "content_values"),
    Variant("text_plus_all_metadata_values", True, "all_values"),
    Variant("text_plus_all_metadata_with_missingness", True, "all_with_missingness"),
)

SPACE_DEFINITIONS = {
    "account_values": (ACCOUNT_BEHAVIOUR_COLUMNS, False),
    "content_values": (CONTENT_STATISTIC_COLUMNS, False),
    "all_values": (ALL_METADATA_COLUMNS, False),
    "all_with_missingness": (ALL_METADATA_COLUMNS, True),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_rows(path: Path) -> dict[str, list[dict[str, str]]]:
    splits = {"train": [], "validation": [], "test": []}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "record_id",
            "source_dataset",
            "text_content",
            "label",
            "partition",
            "split_group_id",
            *ALL_METADATA_COLUMNS,
        }
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            missing = sorted(required - set(reader.fieldnames or []))
            raise ValueError(f"CSV is missing required columns: {missing}")
        seen_ids: set[str] = set()
        group_partitions: dict[str, set[str]] = defaultdict(set)
        for row in reader:
            record_id = (row.get("record_id") or "").strip()
            if not record_id or record_id in seen_ids:
                raise ValueError(f"record_id must be non-empty and unique: {record_id!r}")
            seen_ids.add(record_id)
            partition = row.get("partition")
            if partition not in splits:
                raise ValueError(f"Unexpected partition: {partition!r}")
            if row.get("label") not in {"0", "1"}:
                raise ValueError(f"Unexpected label for {record_id}: {row.get('label')!r}")
            group_id = (row.get("split_group_id") or "").strip()
            if not group_id:
                raise ValueError(f"Missing split_group_id for {record_id}")
            group_partitions[group_id].add(partition)
            splits[partition].append(row)
    if not all(splits.values()):
        raise ValueError("Expected non-empty train, validation and test partitions")
    leaking_groups = sorted(group for group, parts in group_partitions.items() if len(parts) > 1)
    if leaking_groups:
        raise ValueError(f"split_group_id crosses partitions: {leaking_groups[:5]}")
    return splits


def is_missing(value: str | None) -> bool:
    return value is None or value.strip().lower() in {"", "na", "n/a", "nan", "null", "none"}


def parse_numeric(value: str | None, column: str) -> float:
    if is_missing(value):
        return math.nan
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Non-numeric value in {column}: {value!r}") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"Non-finite value in {column}: {value!r}")
    if column in LOG1P_COLUMNS:
        if parsed < 0:
            raise ValueError(f"Negative count-like value in {column}: {value!r}")
        parsed = math.log1p(parsed)
    return parsed


def metadata_array(rows: Sequence[dict[str, str]], columns: Sequence[str]) -> np.ndarray:
    return np.asarray(
        [[parse_numeric(row.get(column), column) for column in columns] for row in rows],
        dtype=np.float64,
    )


class MetadataTransformer:
    def __init__(self, columns: Sequence[str], add_missingness: bool):
        self.columns = tuple(columns)
        self.add_missingness = add_missingness
        self.medians: np.ndarray | None = None
        self.scaler = StandardScaler()

    def fit_transform(self, rows: Sequence[dict[str, str]]) -> sparse.csr_matrix:
        raw = metadata_array(rows, self.columns)
        with np.errstate(all="ignore"):
            medians = np.nanmedian(raw, axis=0)
        medians = np.where(np.isnan(medians), 0.0, medians)
        self.medians = medians
        filled = np.where(np.isnan(raw), medians, raw)
        values = self.scaler.fit_transform(filled)
        return self._combine(values, np.isnan(raw))

    def transform(self, rows: Sequence[dict[str, str]]) -> sparse.csr_matrix:
        if self.medians is None:
            raise RuntimeError("MetadataTransformer must be fitted before transform")
        raw = metadata_array(rows, self.columns)
        filled = np.where(np.isnan(raw), self.medians, raw)
        values = self.scaler.transform(filled)
        return self._combine(values, np.isnan(raw))

    def _combine(self, values: np.ndarray, missing: np.ndarray) -> sparse.csr_matrix:
        if self.add_missingness:
            values = np.hstack([values, missing.astype(np.float64)])
        return sparse.csr_matrix(values)


def make_vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.995,
        max_features=100_000,
        sublinear_tf=True,
    )


def texts(rows: Sequence[dict[str, str]]) -> list[str]:
    return [row.get("text_content") or "" for row in rows]


def labels(rows: Sequence[dict[str, str]]) -> np.ndarray:
    return np.asarray([int(row["label"]) for row in rows], dtype=np.int64)


def fit_feature_spaces(train_rows, evaluation_rows):
    vectorizer = make_vectorizer()
    train_spaces: dict[str, sparse.csr_matrix] = {
        "text": vectorizer.fit_transform(texts(train_rows)).tocsr()
    }
    evaluation_spaces: dict[str, sparse.csr_matrix] = {
        "text": vectorizer.transform(texts(evaluation_rows)).tocsr()
    }
    transformers: dict[str, MetadataTransformer] = {}
    for name, (columns, add_missingness) in SPACE_DEFINITIONS.items():
        transformer = MetadataTransformer(columns, add_missingness)
        train_spaces[name] = transformer.fit_transform(train_rows)
        evaluation_spaces[name] = transformer.transform(evaluation_rows)
        transformers[name] = transformer
    return train_spaces, evaluation_spaces, vectorizer, transformers


def transform_feature_spaces(rows, vectorizer, transformers):
    spaces = {"text": vectorizer.transform(texts(rows)).tocsr()}
    for name, transformer in transformers.items():
        spaces[name] = transformer.transform(rows)
    return spaces


def matrix_for_variant(spaces: dict[str, sparse.csr_matrix], variant: Variant):
    parts = []
    if variant.use_text:
        parts.append(spaces["text"])
    if variant.metadata_space is not None:
        parts.append(spaces[variant.metadata_space])
    if not parts:
        raise ValueError(f"Variant has no features: {variant.name}")
    return parts[0] if len(parts) == 1 else sparse.hstack(parts, format="csr")


def expanded_metrics(y_true, y_pred, y_score=None) -> dict:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )
    result = {
        "row_count": int(len(y_true)),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 6),
        "precision_label_1": round(float(precision), 6),
        "recall_label_1": round(float(recall), 6),
        "f1_label_1": round(float(f1), 6),
        "macro_f1": round(float(f1_score(y_true, y_pred, average="macro", zero_division=0)), 6),
        "balanced_accuracy": round(float(balanced_accuracy_score(y_true, y_pred)), 6),
    }
    if y_score is not None and len(set(int(value) for value in y_true)) == 2:
        result["roc_auc"] = round(float(roc_auc_score(y_true, y_score)), 6)
        result["average_precision"] = round(float(average_precision_score(y_true, y_score)), 6)
    return result


def make_classifier(c_value: float, class_weight: str | None) -> LogisticRegression:
    return LogisticRegression(
        C=c_value,
        class_weight=class_weight,
        solver="liblinear",
        max_iter=1000,
        random_state=RANDOM_STATE,
    )


def select_classifier(train_matrix, train_labels, validation_matrix, validation_labels):
    candidates = []
    best = None
    for class_weight in (None, "balanced"):
        for c_value in (0.25, 0.5, 1.0, 2.0, 4.0):
            classifier = make_classifier(c_value, class_weight)
            classifier.fit(train_matrix, train_labels)
            predictions = classifier.predict(validation_matrix)
            scores = classifier.predict_proba(validation_matrix)[:, 1]
            validation = expanded_metrics(validation_labels, predictions, scores)
            candidate = {
                "C": c_value,
                "class_weight": class_weight,
                "validation": validation,
            }
            candidates.append(candidate)
            selection_score = (validation["f1_label_1"], validation["accuracy"], -c_value)
            if best is None or selection_score > best[0]:
                best = (selection_score, classifier, candidate)
    assert best is not None
    return best[1], best[2], candidates


def evaluate_classifier(classifier, matrix, rows):
    truth = labels(rows)
    predictions = classifier.predict(matrix)
    probabilities = classifier.predict_proba(matrix)[:, 1]
    return expanded_metrics(truth, predictions, probabilities), predictions, probabilities


def evaluate_by_source(predictions, probabilities, rows):
    result = {}
    for source in sorted({row["source_dataset"] for row in rows}):
        indices = np.asarray(
            [index for index, row in enumerate(rows) if row["source_dataset"] == source],
            dtype=np.int64,
        )
        result[source] = expanded_metrics(
            labels([rows[index] for index in indices]),
            predictions[indices],
            probabilities[indices],
        )
    return result


def metadata_missingness_signature(row: dict[str, str]) -> tuple[int, ...]:
    return tuple(int(is_missing(row.get(column))) for column in ALL_METADATA_COLUMNS)


def majority_mapping(train_rows, key_function, target_field):
    counts: dict[object, Counter] = defaultdict(Counter)
    global_counts = Counter()
    for row in train_rows:
        target = row[target_field]
        counts[key_function(row)][target] += 1
        global_counts[target] += 1
    mapping = {
        key: sorted(counter.items(), key=lambda item: (-item[1], item[0]))[0][0]
        for key, counter in counts.items()
    }
    default = sorted(global_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
    return mapping, default


def multiclass_metrics(y_true, y_pred, classes):
    matrix = confusion_matrix(y_true, y_pred, labels=classes)
    return {
        "row_count": len(y_true),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 6),
        "macro_f1": round(float(f1_score(y_true, y_pred, average="macro", zero_division=0)), 6),
        "balanced_accuracy": round(float(balanced_accuracy_score(y_true, y_pred)), 6),
        "classes": list(classes),
        "confusion_matrix": matrix.astype(int).tolist(),
    }


def source_from_missingness_diagnostic(train_rows, evaluation_rows):
    mapping, default = majority_mapping(train_rows, metadata_missingness_signature, "source_dataset")
    classes = sorted({row["source_dataset"] for row in train_rows + evaluation_rows})
    truth = [row["source_dataset"] for row in evaluation_rows]
    predicted = [mapping.get(metadata_missingness_signature(row), default) for row in evaluation_rows]
    majority = [default] * len(evaluation_rows)
    return {
        "signature_count_in_train": len(mapping),
        "unknown_signature_count": sum(
            metadata_missingness_signature(row) not in mapping for row in evaluation_rows
        ),
        "missingness_signature_predictor": multiclass_metrics(truth, predicted, classes),
        "global_majority_source_baseline": multiclass_metrics(truth, majority, classes),
    }


def source_majority_label_diagnostic(train_rows, evaluation_rows):
    mapping, default = majority_mapping(train_rows, lambda row: row["source_dataset"], "label")
    truth = labels(evaluation_rows)
    predicted = np.asarray(
        [int(mapping.get(row["source_dataset"], default)) for row in evaluation_rows], dtype=np.int64
    )
    return expanded_metrics(truth, predicted)


def missingness_profile(rows):
    def profile(group):
        return {
            column: {
                "missing_count": sum(is_missing(row.get(column)) for row in group),
                "missing_ratio": round(
                    sum(is_missing(row.get(column)) for row in group) / len(group), 6
                ),
            }
            for column in ALL_METADATA_COLUMNS
        }

    by_source = {
        source: profile([row for row in rows if row["source_dataset"] == source])
        for source in sorted({row["source_dataset"] for row in rows})
    }
    return {"overall": profile(rows), "by_source_dataset": by_source}


def paired_comparison(reference_predictions, candidate_predictions, truth):
    reference_correct = reference_predictions == truth
    candidate_correct = candidate_predictions == truth
    fixed = int(np.sum(~reference_correct & candidate_correct))
    regressions = int(np.sum(reference_correct & ~candidate_correct))
    discordant = fixed + regressions
    p_value = 1.0 if discordant == 0 else float(
        binomtest(min(fixed, regressions), discordant, 0.5, alternative="two-sided").pvalue
    )
    return {
        "reference_errors_fixed": fixed,
        "reference_correct_regressed": regressions,
        "net_errors_removed": fixed - regressions,
        "discordant_pair_count": discordant,
        "mcnemar_exact_two_sided_p_value": p_value,
        "statistically_significant_at_0_05": p_value < 0.05,
    }


def mean_across_sources(results):
    metric_names = (
        "accuracy",
        "f1_label_1",
        "macro_f1",
        "balanced_accuracy",
        "roc_auc",
        "average_precision",
    )
    return {
        metric: round(statistics.mean(item["metrics"][metric] for item in results.values()), 6)
        for metric in metric_names
    }


def leave_one_source_out(splits, selected_hyperparameters):
    sources = sorted({row["source_dataset"] for rows in splits.values() for row in rows})
    results = {variant.name: {} for variant in VARIANTS}
    for held_out in sources:
        train_rows = [row for row in splits["train"] if row["source_dataset"] != held_out]
        test_rows = [row for row in splits["test"] if row["source_dataset"] == held_out]
        train_spaces, test_spaces, _, _ = fit_feature_spaces(train_rows, test_rows)
        train_truth = labels(train_rows)
        for variant in VARIANTS:
            hyperparameters = selected_hyperparameters[variant.name]
            classifier = make_classifier(
                float(hyperparameters["C"]), hyperparameters["class_weight"]
            )
            classifier.fit(matrix_for_variant(train_spaces, variant), train_truth)
            metrics, _, _ = evaluate_classifier(
                classifier, matrix_for_variant(test_spaces, variant), test_rows
            )
            results[variant.name][held_out] = {
                "train_rows_from_other_sources": len(train_rows),
                "held_out_test_rows": len(test_rows),
                "metrics": metrics,
            }
    return results


def write_predictions(path, rows, predictions, probabilities):
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for index, row in enumerate(rows):
            record = {
                "record_id": row["record_id"],
                "partition": "test",
                "source_dataset": row["source_dataset"],
                "source_label": int(row["label"]),
                "predictions": {
                    name: {
                        "predicted_label": int(predictions[name][index]),
                        "score_label_1": round(float(probabilities[name][index]), 10),
                    }
                    for name in predictions
                },
            }
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--run-at",
        help="Optional fixed ISO-8601 timestamp for bit-for-bit reproduction of a frozen run.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Explicitly allow replacement of existing output artifacts.",
    )
    args = parser.parse_args()

    results_path = args.output_dir / "metadata_ablation_results_v1.json"
    predictions_path = args.output_dir / "metadata_ablation_test_predictions_v1.jsonl"
    existing_outputs = [path for path in (results_path, predictions_path) if path.exists()]
    if existing_outputs and not args.overwrite:
        raise FileExistsError(
            "Refusing to overwrite frozen-style artifacts without --overwrite: "
            + ", ".join(str(path) for path in existing_outputs)
        )
    if args.run_at:
        parsed_run_at = datetime.fromisoformat(args.run_at.replace("Z", "+00:00"))
        if parsed_run_at.tzinfo is None:
            raise ValueError("--run-at must include a timezone offset")
        run_at = parsed_run_at.isoformat()
    else:
        run_at = datetime.now(timezone.utc).isoformat()

    splits = read_rows(args.input)
    input_hash = sha256_file(args.input)
    train_rows = splits["train"]
    validation_rows = splits["validation"]

    # Phase 1: fit transforms on train and select every configuration on validation.
    train_spaces, validation_spaces, vectorizer, transformers = fit_feature_spaces(
        train_rows, validation_rows
    )
    train_truth = labels(train_rows)
    validation_truth = labels(validation_rows)
    fitted_classifiers = {}
    variants_report = {}
    selected_hyperparameters = {}
    for variant in VARIANTS:
        classifier, selected, candidates = select_classifier(
            matrix_for_variant(train_spaces, variant),
            train_truth,
            matrix_for_variant(validation_spaces, variant),
            validation_truth,
        )
        fitted_classifiers[variant.name] = classifier
        selected_hyperparameters[variant.name] = {
            "C": selected["C"],
            "class_weight": selected["class_weight"],
            "solver": "liblinear",
            "threshold": 0.5,
        }
        validation_predictions = classifier.predict(
            matrix_for_variant(validation_spaces, variant)
        )
        validation_probabilities = classifier.predict_proba(
            matrix_for_variant(validation_spaces, variant)
        )[:, 1]
        variants_report[variant.name] = {
            "feature_policy": {
                "uses_text_content": variant.use_text,
                "metadata_space": variant.metadata_space,
                "metadata_columns": list(
                    SPACE_DEFINITIONS[variant.metadata_space][0]
                    if variant.metadata_space is not None
                    else []
                ),
                "explicit_missingness_indicators": bool(
                    variant.metadata_space is not None
                    and SPACE_DEFINITIONS[variant.metadata_space][1]
                ),
                "prohibited_predictive_fields": sorted(PROHIBITED_PREDICTIVE_FIELDS),
            },
            "selected_hyperparameters": selected_hyperparameters[variant.name],
            "selection_candidates": candidates,
            "validation": selected["validation"],
            "validation_by_source_dataset": evaluate_by_source(
                validation_predictions, validation_probabilities, validation_rows
            ),
        }

    # Phase 2: configurations are frozen; test is transformed and evaluated once.
    test_rows = splits["test"]
    test_spaces = transform_feature_spaces(test_rows, vectorizer, transformers)
    test_truth = labels(test_rows)
    test_predictions = {}
    test_probabilities = {}
    for variant in VARIANTS:
        test_metrics, predictions, probabilities = evaluate_classifier(
            fitted_classifiers[variant.name], matrix_for_variant(test_spaces, variant), test_rows
        )
        variants_report[variant.name]["test"] = test_metrics
        variants_report[variant.name]["test_by_source_dataset"] = evaluate_by_source(
            predictions, probabilities, test_rows
        )
        test_predictions[variant.name] = predictions
        test_probabilities[variant.name] = probabilities

    cross_source = leave_one_source_out(splits, selected_hyperparameters)
    for variant in VARIANTS:
        variants_report[variant.name]["leave_one_source_out"] = cross_source[variant.name]
        variants_report[variant.name]["leave_one_source_out_mean_across_sources"] = (
            mean_across_sources(cross_source[variant.name])
        )

    text_predictions = test_predictions["text_only"]
    paired = {
        name: paired_comparison(text_predictions, predictions, test_truth)
        for name, predictions in test_predictions.items()
        if name.startswith("text_plus_")
    }

    validation_ranked_combined = sorted(
        [variant.name for variant in VARIANTS if variant.name.startswith("text_plus_")],
        key=lambda name: (
            variants_report[name]["validation"]["f1_label_1"],
            variants_report[name]["validation"]["accuracy"],
            name,
        ),
        reverse=True,
    )
    selected_combined = validation_ranked_combined[0]
    text_loso = variants_report["text_only"]["leave_one_source_out_mean_across_sources"]
    combined_loso = variants_report[selected_combined]["leave_one_source_out_mean_across_sources"]
    source_diagnostics = {
        "purpose": "Quantify source confounding; source_dataset is never supplied to a fraud-label model.",
        "validation": source_from_missingness_diagnostic(train_rows, validation_rows),
        "test": source_from_missingness_diagnostic(train_rows, test_rows),
        "source_majority_label_baseline_validation": source_majority_label_diagnostic(
            train_rows, validation_rows
        ),
        "source_majority_label_baseline_test": source_majority_label_diagnostic(
            train_rows, test_rows
        ),
    }

    explicit_missingness_source_macro_f1 = source_diagnostics["validation"][
        "missingness_signature_predictor"
    ]["macro_f1"]
    combined_improves_internal = (
        variants_report[selected_combined]["test"]["macro_f1"]
        > variants_report["text_only"]["test"]["macro_f1"]
    )
    combined_improves_cross_source = combined_loso["macro_f1"] > text_loso["macro_f1"]
    high_source_leakage_risk = explicit_missingness_source_macro_f1 >= 0.5
    promote = combined_improves_internal and combined_improves_cross_source and not high_source_leakage_risk

    report = {
        "analysis_id": "MENDELEY_METADATA_ABLATION_V1",
        "run_at": run_at,
        "status": "FROZEN_RESEARCH_ABLATION_NOT_FOR_DEPLOYMENT",
        "label_semantics": LABEL_SEMANTICS,
        "data": {
            "input": str(args.input),
            "input_sha256": input_hash,
            "partition_counts": {name: len(rows) for name, rows in splits.items()},
            "source_counts": dict(
                sorted(Counter(row["source_dataset"] for rows in splits.values() for row in rows).items())
            ),
            "split_group_cross_partition_count": 0,
        },
        "selection_policy": {
            "selection_partitions": ["train", "validation"],
            "test_used_for_feature_fitting": False,
            "test_used_for_hyperparameter_or_variant_selection": False,
            "candidate_hyperparameters": {
                "C": [0.25, 0.5, 1.0, 2.0, 4.0],
                "class_weight": [None, "balanced"],
            },
            "primary_selection_metric": "validation f1_label_1; ties by validation accuracy then lower C",
            "selected_combined_variant_on_validation": selected_combined,
        },
        "preprocessing": {
            "metadata_imputation": "per-column median fitted on the current training rows only",
            "metadata_scaling": "StandardScaler fitted on median-imputed training values only",
            "count_transform": "log1p for non-negative count-like columns",
            "text_vectorizer": {
                "type": "tfidf",
                "ngram_range": [1, 2],
                "min_df": 2,
                "max_df": 0.995,
                "max_features": 100000,
                "sublinear_tf": True,
                "full_train_vocabulary_size": len(vectorizer.vocabulary_),
            },
        },
        "metadata_contract": {
            "account_behaviour_columns": list(ACCOUNT_BEHAVIOUR_COLUMNS),
            "content_statistic_columns": list(CONTENT_STATISTIC_COLUMNS),
            "all_metadata_columns": list(ALL_METADATA_COLUMNS),
            "prohibited_predictive_fields": sorted(PROHIBITED_PREDICTIVE_FIELDS),
            "source_dataset_predictive_use": False,
        },
        "missingness_profile": missingness_profile(
            [row for rows in splits.values() for row in rows]
        ),
        "source_confounding_diagnostics": source_diagnostics,
        "variants": variants_report,
        "paired_test_comparisons_against_text_only": paired,
        "decision": {
            "selected_combined_variant_on_validation": selected_combined,
            "combined_internal_test_macro_f1_improves": combined_improves_internal,
            "combined_leave_one_source_out_macro_f1_improves": combined_improves_cross_source,
            "metadata_missingness_high_source_leakage_risk": high_source_leakage_risk,
            "promote_metadata_to_primary_baseline": promote,
            "policy": (
                "Metadata can replace the frozen text baseline only if the validation-selected combined "
                "variant improves internal-test and leave-one-source-out macro-F1 and the missingness-only "
                "source diagnostic is below 0.50 macro-F1. This is a conservative research gate, not a "
                "deployment criterion."
            ),
        },
        "prohibited_claims": [
            "Do not describe source label 1 as regulator-verified investment fraud.",
            "Do not describe model scores as real-world scam probabilities.",
            "Do not treat source-specific missingness as a legitimate behavioural signal.",
            "Do not deploy this research ablation for blocking, enforcement or financial decisions.",
        ],
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    results_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_predictions(
        predictions_path, test_rows, test_predictions, test_probabilities
    )
    print(json.dumps({
        "analysis_id": report["analysis_id"],
        "input_sha256": input_hash,
        "selected_combined_variant_on_validation": selected_combined,
        "decision": report["decision"],
        "text_only": {
            "validation": variants_report["text_only"]["validation"],
            "test": variants_report["text_only"]["test"],
            "leave_one_source_out_mean": text_loso,
        },
        "selected_combined": {
            "validation": variants_report[selected_combined]["validation"],
            "test": variants_report[selected_combined]["test"],
            "leave_one_source_out_mean": combined_loso,
        },
        "missingness_source_diagnostic_validation": source_diagnostics["validation"],
        "outputs": {
            "results": str(results_path),
            "predictions": str(predictions_path),
        },
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
