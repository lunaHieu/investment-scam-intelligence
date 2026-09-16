"""Compare word, character, and combined TF-IDF text representations.

All feature extractors are fitted on training text only. The downstream classifier
is frozen so the ablation measures representation effects. A promotion-eligible
representation is selected on validation before internal test is transformed.
source_dataset is never a predictive feature; it is used only for diagnostics,
stratified reporting, and leave-one-source-out evaluation.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import warnings
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy import sparse
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import pairwise_distances_chunked
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import normalize

from analyze_mendeley_metadata_ablation import (
    LABEL_SEMANTICS,
    RANDOM_STATE,
    evaluate_by_source,
    evaluate_classifier,
    expanded_metrics,
    labels,
    make_classifier,
    make_vectorizer,
    multiclass_metrics,
    read_rows,
    sha256_file,
    texts,
)
from analyze_mendeley_source_balance_ablation import source_summary
from audit_mendeley_text_overlap import (
    normalize_near_template_v2 as diagnostic_normalize_template,
)


ANALYSIS_ID = "MENDELEY_TEXT_REPRESENTATION_ABLATION_V1"
BASELINE_REPRESENTATION = "word_1_2"
REPRESENTATIONS = (
    BASELINE_REPRESENTATION,
    "char_wb_3_5",
    "char_3_5",
    "word_1_2_plus_char_wb_3_5",
)
PROMOTION_ELIGIBLE_REPRESENTATIONS = (
    BASELINE_REPRESENTATION,
    "char_wb_3_5",
    "word_1_2_plus_char_wb_3_5",
)
FROZEN_C = 2.0
FROZEN_CLASS_WEIGHT = None
CHAR_MAX_FEATURES = 100_000
BOOTSTRAP_REPLICATES = 10_000


def make_character_vectorizer(analyzer: str) -> TfidfVectorizer:
    if analyzer not in {"char", "char_wb"}:
        raise ValueError(f"Unsupported character analyzer: {analyzer}")
    return TfidfVectorizer(
        analyzer=analyzer,
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(3, 5),
        min_df=2,
        max_df=0.995,
        max_features=CHAR_MAX_FEATURES,
        sublinear_tf=True,
    )


def combine_and_normalize(left, right):
    combined = sparse.hstack([left, right], format="csr")
    return normalize(combined, norm="l2", copy=False)


def fit_representation_spaces(
    train_rows, evaluation_rows, representations=REPRESENTATIONS
):
    train_text = texts(train_rows)
    evaluation_text = texts(evaluation_rows)
    requested = tuple(representations)
    vectorizers = {}
    if any(name in requested for name in ("word_1_2", "word_1_2_plus_char_wb_3_5")):
        vectorizers["word"] = make_vectorizer()
    if any(name in requested for name in ("char_wb_3_5", "word_1_2_plus_char_wb_3_5")):
        vectorizers["char_wb"] = make_character_vectorizer("char_wb")
    if "char_3_5" in requested:
        vectorizers["char"] = make_character_vectorizer("char")
    train_base = {}
    evaluation_base = {}
    for name, vectorizer in vectorizers.items():
        train_base[name] = vectorizer.fit_transform(train_text).tocsr()
        evaluation_base[name] = vectorizer.transform(evaluation_text).tocsr()
    train_spaces = {}
    evaluation_spaces = {}
    if "word_1_2" in requested:
        train_spaces["word_1_2"] = train_base["word"]
        evaluation_spaces["word_1_2"] = evaluation_base["word"]
    if "char_wb_3_5" in requested:
        train_spaces["char_wb_3_5"] = train_base["char_wb"]
        evaluation_spaces["char_wb_3_5"] = evaluation_base["char_wb"]
    if "char_3_5" in requested:
        train_spaces["char_3_5"] = train_base["char"]
        evaluation_spaces["char_3_5"] = evaluation_base["char"]
    if "word_1_2_plus_char_wb_3_5" in requested:
        train_spaces["word_1_2_plus_char_wb_3_5"] = combine_and_normalize(
            train_base["word"], train_base["char_wb"]
        )
        evaluation_spaces["word_1_2_plus_char_wb_3_5"] = combine_and_normalize(
            evaluation_base["word"], evaluation_base["char_wb"]
        )
    return train_spaces, evaluation_spaces, vectorizers


def transform_representation_spaces(rows, vectorizers, representations=REPRESENTATIONS):
    row_text = texts(rows)
    requested = tuple(representations)
    required_base = set()
    if any(name in requested for name in ("word_1_2", "word_1_2_plus_char_wb_3_5")):
        required_base.add("word")
    if any(name in requested for name in ("char_wb_3_5", "word_1_2_plus_char_wb_3_5")):
        required_base.add("char_wb")
    if "char_3_5" in requested:
        required_base.add("char")
    base = {
        name: vectorizers[name].transform(row_text).tocsr()
        for name in sorted(required_base)
    }
    result = {}
    if "word_1_2" in requested:
        result["word_1_2"] = base["word"]
    if "char_wb_3_5" in requested:
        result["char_wb_3_5"] = base["char_wb"]
    if "char_3_5" in requested:
        result["char_3_5"] = base["char"]
    if "word_1_2_plus_char_wb_3_5" in requested:
        result["word_1_2_plus_char_wb_3_5"] = combine_and_normalize(
            base["word"], base["char_wb"]
        )
    return result


def representation_feature_names(representation, vectorizers) -> np.ndarray:
    if representation == "word_1_2":
        return np.asarray(
            [f"word:{name}" for name in vectorizers["word"].get_feature_names_out()],
            dtype=object,
        )
    if representation == "char_wb_3_5":
        return np.asarray(
            [f"char_wb:{name}" for name in vectorizers["char_wb"].get_feature_names_out()],
            dtype=object,
        )
    if representation == "char_3_5":
        return np.asarray(
            [f"char:{name}" for name in vectorizers["char"].get_feature_names_out()],
            dtype=object,
        )
    if representation == "word_1_2_plus_char_wb_3_5":
        return np.concatenate([
            representation_feature_names("word_1_2", vectorizers),
            representation_feature_names("char_wb_3_5", vectorizers),
        ])
    raise ValueError(f"Unknown representation: {representation}")


def safe_feature_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")


def top_coefficients(classifier, feature_names, count=30) -> dict:
    coefficients = classifier.coef_[0]
    if len(coefficients) != len(feature_names):
        raise ValueError("Feature-name and coefficient counts do not match")
    positive_indices = np.argsort(coefficients)[-count:][::-1]
    negative_indices = np.argsort(coefficients)[:count]
    return {
        "toward_label_1": [
            {
                "feature": safe_feature_text(str(feature_names[index])),
                "coefficient": round(float(coefficients[index]), 8),
            }
            for index in positive_indices
        ],
        "toward_label_0": [
            {
                "feature": safe_feature_text(str(feature_names[index])),
                "coefficient": round(float(coefficients[index]), 8),
            }
            for index in negative_indices
        ],
    }


def representation_score(name: str, report: dict) -> tuple:
    summary = report["validation_source_summary"]
    return (
        summary["unweighted_mean_macro_f1_across_sources"],
        summary["worst_source_macro_f1"],
        report["validation"]["macro_f1"],
        -PROMOTION_ELIGIBLE_REPRESENTATIONS.index(name),
    )


def fit_frozen_classifier(train_matrix, train_truth):
    classifier = make_classifier(FROZEN_C, FROZEN_CLASS_WEIGHT)
    if len(np.unique(train_truth)) > 2:
        classifier = OneVsRestClassifier(classifier)
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        classifier.fit(train_matrix, train_truth)
    return classifier


def source_predictability_diagnostic(
    train_matrix, train_rows, validation_matrix, validation_rows
) -> dict:
    classes = sorted({row["source_dataset"] for row in train_rows + validation_rows})
    train_targets = np.asarray([row["source_dataset"] for row in train_rows], dtype=object)
    validation_targets = np.asarray(
        [row["source_dataset"] for row in validation_rows], dtype=object
    )
    classifier = fit_frozen_classifier(train_matrix, train_targets)
    predictions = classifier.predict(validation_matrix)
    majority_source = Counter(train_targets).most_common(1)[0][0]
    majority_predictions = np.full(len(validation_targets), majority_source, dtype=object)
    return {
        "purpose": "diagnose how strongly the text representation encodes source identity",
        "source_dataset_used_as_downstream_label_only": True,
        "source_dataset_in_scam_feature_matrix": False,
        "frozen_logistic_regression": {
            "C": FROZEN_C,
            "class_weight": FROZEN_CLASS_WEIGHT,
            "solver": "liblinear",
            "multiclass_strategy": "explicit one-vs-rest",
        },
        "validation": multiclass_metrics(
            validation_targets, predictions, classes
        ),
        "global_majority_source_baseline": multiclass_metrics(
            validation_targets, majority_predictions, classes
        ),
    }


def within_source_label_shuffle(train_rows) -> np.ndarray:
    shuffled = labels(train_rows).copy()
    rng = np.random.default_rng(RANDOM_STATE)
    for source in sorted({row["source_dataset"] for row in train_rows}):
        indices = np.asarray(
            [
                index
                for index, row in enumerate(train_rows)
                if row["source_dataset"] == source
            ],
            dtype=np.int64,
        )
        values = shuffled[indices].copy()
        rng.shuffle(values)
        shuffled[indices] = values
    return shuffled


def label_shuffle_diagnostic(
    train_matrix, train_rows, validation_matrix, validation_rows
) -> dict:
    shuffled_truth = within_source_label_shuffle(train_rows)
    classifier = fit_frozen_classifier(train_matrix, shuffled_truth)
    validation, predictions, probabilities = evaluate_classifier(
        classifier, validation_matrix, validation_rows
    )
    by_source = evaluate_by_source(predictions, probabilities, validation_rows)
    return {
        "purpose": (
            "measure label performance retained from source identity and within-source "
            "label prevalence after destroying within-source text-label association"
        ),
        "shuffle_scope": "training labels independently permuted within each source_dataset",
        "random_state": RANDOM_STATE,
        "validation": validation,
        "validation_by_source_dataset": by_source,
        "validation_source_summary": source_summary(by_source),
    }


def nearest_train_cosine_similarity(train_matrix, evaluation_matrix) -> np.ndarray:
    maxima = []
    for distances in pairwise_distances_chunked(
        evaluation_matrix,
        train_matrix,
        metric="cosine",
        n_jobs=1,
        working_memory=256,
    ):
        maxima.append(1.0 - np.min(distances, axis=1))
    if not maxima:
        return np.asarray([], dtype=np.float64)
    return np.clip(np.concatenate(maxima), 0.0, 1.0)


def similarity_summary(similarities: np.ndarray, rows) -> dict:
    def summarize(values: np.ndarray) -> dict:
        return {
            "row_count": int(len(values)),
            "mean": round(float(np.mean(values)), 6),
            "median": round(float(np.median(values)), 6),
            "p95": round(float(np.quantile(values, 0.95)), 6),
            "maximum": round(float(np.max(values)), 6),
            "count_gte_0_90": int(np.sum(values >= 0.90)),
            "count_gte_0_95": int(np.sum(values >= 0.95)),
            "count_gte_0_99": int(np.sum(values >= 0.99)),
        }

    result = {"overall": summarize(similarities), "by_source_dataset": {}}
    for source in sorted({row["source_dataset"] for row in rows}):
        indices = np.asarray(
            [index for index, row in enumerate(rows) if row["source_dataset"] == source],
            dtype=np.int64,
        )
        result["by_source_dataset"][source] = summarize(similarities[indices])
    return result


def normalized_template_partition_diagnostic(splits) -> dict:
    all_rows = [row for partition in ("train", "validation", "test") for row in splits[partition]]
    groups = defaultdict(list)
    for row in all_rows:
        groups[diagnostic_normalize_template(row.get("text_content") or "")].append(row)
    cross_partition = {
        key: rows
        for key, rows in groups.items()
        if len({row["partition"] for row in rows}) > 1
    }
    train_keys_by_source = {
        source: {
            diagnostic_normalize_template(row.get("text_content") or "")
            for row in splits["train"]
            if row["source_dataset"] == source
        }
        for source in sorted({row["source_dataset"] for row in all_rows})
    }
    match_train_by_source = {}
    for partition in ("validation", "test"):
        match_train_by_source[partition] = {}
        for source, train_keys in train_keys_by_source.items():
            target = [
                row for row in splits[partition] if row["source_dataset"] == source
            ]
            matches = sum(
                diagnostic_normalize_template(row.get("text_content") or "")
                in train_keys
                for row in target
            )
            match_train_by_source[partition][source] = {
                "matching_rows": matches,
                "source_rows": len(target),
                "matching_ratio": round(matches / len(target), 6),
            }
    return {
        "purpose": "diagnose near-template leakage not captured by split_group_id",
        "normalizer": [
            "Unicode NFKC and lowercase",
            "replace live URL, email, @handle, and known bracket placeholders",
            "replace each digit run with 0",
            "collapse whitespace",
        ],
        "normalizer_used_to_build_current_split": False,
        "cross_partition_normalized_template_count": len(cross_partition),
        "affected_row_count": sum(len(rows) for rows in cross_partition.values()),
        "affected_sources": sorted(
            {row["source_dataset"] for rows in cross_partition.values() for row in rows}
        ),
        "label_conflict_template_count": sum(
            len({row["label"] for row in rows}) > 1 for rows in cross_partition.values()
        ),
        "same_source_match_to_train": match_train_by_source,
        "warning": (
            "This is a diagnostic only. Any future text normalization experiment must rebuild "
            "split_group_id with the same normalizer before model evaluation."
        ),
    }


def macro_f1_from_confusion(values: np.ndarray) -> float:
    tn, fp, fn, tp = (float(value) for value in values)
    denominator_0 = 2.0 * tn + fp + fn
    denominator_1 = 2.0 * tp + fp + fn
    f1_0 = 0.0 if denominator_0 == 0 else 2.0 * tn / denominator_0
    f1_1 = 0.0 if denominator_1 == 0 else 2.0 * tp / denominator_1
    return (f1_0 + f1_1) / 2.0


def paired_group_bootstrap(
    reference_predictions,
    candidate_predictions,
    truth,
    group_ids,
    replicates=BOOTSTRAP_REPLICATES,
) -> dict:
    unique_groups = sorted(set(group_ids))
    group_index = {group_id: index for index, group_id in enumerate(unique_groups)}
    reference_counts = np.zeros((len(unique_groups), 4), dtype=np.int64)
    candidate_counts = np.zeros((len(unique_groups), 4), dtype=np.int64)
    group_sizes = np.zeros(len(unique_groups), dtype=np.int64)

    def confusion_index(actual: int, predicted: int) -> int:
        return {(0, 0): 0, (0, 1): 1, (1, 0): 2, (1, 1): 3}[(actual, predicted)]

    for actual, reference, candidate, group_id in zip(
        truth, reference_predictions, candidate_predictions, group_ids
    ):
        index = group_index[group_id]
        group_sizes[index] += 1
        reference_counts[index, confusion_index(int(actual), int(reference))] += 1
        candidate_counts[index, confusion_index(int(actual), int(candidate))] += 1

    reference_point = macro_f1_from_confusion(reference_counts.sum(axis=0))
    candidate_point = macro_f1_from_confusion(candidate_counts.sum(axis=0))
    rng = np.random.default_rng(RANDOM_STATE)
    differences = np.empty(replicates, dtype=np.float64)
    for replicate in range(replicates):
        sampled = rng.integers(0, len(unique_groups), size=len(unique_groups))
        differences[replicate] = (
            macro_f1_from_confusion(candidate_counts[sampled].sum(axis=0))
            - macro_f1_from_confusion(reference_counts[sampled].sum(axis=0))
        )
    lower, upper = np.quantile(differences, [0.025, 0.975])
    return {
        "unit": "split_group_id",
        "cluster_count": len(unique_groups),
        "row_count": int(len(truth)),
        "largest_cluster_rows": int(group_sizes.max()),
        "replicates": int(replicates),
        "random_state": RANDOM_STATE,
        "reference_macro_f1": round(reference_point, 6),
        "candidate_macro_f1": round(candidate_point, 6),
        "macro_f1_difference": round(candidate_point - reference_point, 6),
        "difference_percentile_95_ci": [round(float(lower), 6), round(float(upper), 6)],
        "probability_candidate_difference_gt_0": round(
            float(np.mean(differences > 0.0)), 6
        ),
        "ci_lower_bound_gt_0": bool(lower > 0.0),
    }


def mean_across_held_out_sources(results: dict) -> dict:
    metrics = (
        "accuracy",
        "f1_label_1",
        "macro_f1",
        "balanced_accuracy",
        "roc_auc",
        "average_precision",
    )
    return {
        metric: round(statistics.mean(item["metrics"][metric] for item in results.values()), 6)
        for metric in metrics
    }


def leave_one_source_out(splits, evaluated_representations):
    sources = sorted({row["source_dataset"] for rows in splits.values() for row in rows})
    results = {representation: {} for representation in evaluated_representations}
    for held_out in sources:
        train_rows = [row for row in splits["train"] if row["source_dataset"] != held_out]
        test_rows = [row for row in splits["test"] if row["source_dataset"] == held_out]
        train_spaces, test_spaces, _ = fit_representation_spaces(
            train_rows, test_rows, evaluated_representations
        )
        train_truth = labels(train_rows)
        for representation in evaluated_representations:
            classifier = fit_frozen_classifier(train_spaces[representation], train_truth)
            metrics, _, _ = evaluate_classifier(
                classifier, test_spaces[representation], test_rows
            )
            results[representation][held_out] = {
                "train_rows_from_other_sources": len(train_rows),
                "held_out_test_rows": len(test_rows),
                "metrics": metrics,
            }
    return results


def metrics_below_similarity_threshold(
    predictions, probabilities, rows, similarities, threshold
) -> dict:
    indices = np.flatnonzero(similarities < threshold)
    excluded = int(len(rows) - len(indices))
    if not len(indices):
        return {"row_count": 0, "excluded_row_count": excluded, "metrics": None}
    subset_rows = [rows[int(index)] for index in indices]
    return {
        "row_count": int(len(indices)),
        "excluded_row_count": excluded,
        "metrics": expanded_metrics(
            labels(subset_rows), predictions[indices], probabilities[indices]
        ),
    }


def write_predictions(path, rows, predictions, probabilities, evaluated_representations):
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for index, row in enumerate(rows):
            record = {
                "record_id": row["record_id"],
                "split_group_id": row["split_group_id"],
                "partition": "test",
                "source_dataset": row["source_dataset"],
                "source_label": int(row["label"]),
                "predictions": {
                    representation: {
                        "predicted_label": int(predictions[representation][index]),
                        "score_label_1": round(float(probabilities[representation][index]), 10),
                    }
                    for representation in evaluated_representations
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

    results_path = args.output_dir / "text_representation_ablation_results_v1.json"
    predictions_path = args.output_dir / "text_representation_ablation_test_predictions_v1.jsonl"
    existing = [path for path in (results_path, predictions_path) if path.exists()]
    if existing and not args.overwrite:
        raise FileExistsError(
            "Refusing to overwrite frozen-style artifacts without --overwrite: "
            + ", ".join(str(path) for path in existing)
        )
    if args.run_at:
        parsed_run_at = datetime.fromisoformat(args.run_at.replace("Z", "+00:00"))
        if parsed_run_at.tzinfo is None:
            raise ValueError("--run-at must include a timezone offset")
        run_at = parsed_run_at.isoformat()
    else:
        run_at = datetime.now(timezone.utc).isoformat()

    splits = read_rows(args.input)
    train_rows = splits["train"]
    validation_rows = splits["validation"]
    template_partition_diagnostic = normalized_template_partition_diagnostic(splits)

    # Phase 1: fit on train, evaluate every representation on validation, then freeze winner.
    train_spaces, validation_spaces, vectorizers = fit_representation_spaces(
        train_rows, validation_rows
    )
    train_truth = labels(train_rows)
    classifiers = {}
    representations_report = {}
    for representation in REPRESENTATIONS:
        classifier = fit_frozen_classifier(train_spaces[representation], train_truth)
        validation, predictions, probabilities = evaluate_classifier(
            classifier, validation_spaces[representation], validation_rows
        )
        validation_by_source = evaluate_by_source(
            predictions, probabilities, validation_rows
        )
        hyperparameters = {
            "C": FROZEN_C,
            "class_weight": FROZEN_CLASS_WEIGHT,
            "solver": "liblinear",
            "threshold": 0.5,
        }
        classifiers[representation] = classifier
        feature_names = representation_feature_names(representation, vectorizers)
        if len(feature_names) != train_spaces[representation].shape[1]:
            raise ValueError(f"Feature-name count mismatch for {representation}")
        representations_report[representation] = {
            "feature_count": int(train_spaces[representation].shape[1]),
            "train_nnz": int(train_spaces[representation].nnz),
            "validation_nnz": int(validation_spaces[representation].nnz),
            "hit_max_features_cap": bool(
                representation == "char_3_5"
                and len(vectorizers["char"].vocabulary_) == CHAR_MAX_FEATURES
            ),
            "frozen_classifier": hyperparameters,
            "validation": validation,
            "validation_by_source_dataset": validation_by_source,
            "validation_source_summary": source_summary(validation_by_source),
            "validation_source_predictability_diagnostic": (
                source_predictability_diagnostic(
                    train_spaces[representation],
                    train_rows,
                    validation_spaces[representation],
                    validation_rows,
                )
            ),
            "within_source_label_shuffle_diagnostic": label_shuffle_diagnostic(
                train_spaces[representation],
                train_rows,
                validation_spaces[representation],
                validation_rows,
            ),
            "top_coefficients": top_coefficients(classifier, feature_names),
        }

    selected_representation = max(
        PROMOTION_ELIGIBLE_REPRESENTATIONS,
        key=lambda name: representation_score(name, representations_report[name]),
    )
    evaluated_representations = (
        (BASELINE_REPRESENTATION,)
        if selected_representation == BASELINE_REPRESENTATION
        else (BASELINE_REPRESENTATION, selected_representation)
    )
    validation_char_similarities = nearest_train_cosine_similarity(
        train_spaces["char_wb_3_5"], validation_spaces["char_wb_3_5"]
    )

    # Phase 2: selection is frozen; open test only for the baseline and selected challenger.
    test_rows = splits["test"]
    test_spaces = transform_representation_spaces(
        test_rows, vectorizers, evaluated_representations
    )
    test_truth = labels(test_rows)
    test_predictions = {}
    test_probabilities = {}
    for representation in evaluated_representations:
        test, predictions, probabilities = evaluate_classifier(
            classifiers[representation], test_spaces[representation], test_rows
        )
        test_by_source = evaluate_by_source(predictions, probabilities, test_rows)
        representations_report[representation]["test"] = test
        representations_report[representation]["test_by_source_dataset"] = test_by_source
        representations_report[representation]["test_source_summary"] = source_summary(
            test_by_source
        )
        test_predictions[representation] = predictions
        test_probabilities[representation] = probabilities

    test_char_wb = vectorizers["char_wb"].transform(texts(test_rows)).tocsr()
    test_char_similarities = nearest_train_cosine_similarity(
        train_spaces["char_wb_3_5"], test_char_wb
    )
    for representation in evaluated_representations:
        representations_report[representation][
            "test_metrics_after_excluding_near_train_char_wb_matches"
        ] = {
            "similarity_lt_0_95": metrics_below_similarity_threshold(
                test_predictions[representation],
                test_probabilities[representation],
                test_rows,
                test_char_similarities,
                0.95,
            ),
            "similarity_lt_0_99": metrics_below_similarity_threshold(
                test_predictions[representation],
                test_probabilities[representation],
                test_rows,
                test_char_similarities,
                0.99,
            ),
        }

    cross_source = leave_one_source_out(splits, evaluated_representations)
    for representation in evaluated_representations:
        representations_report[representation]["leave_one_source_out"] = cross_source[
            representation
        ]
        representations_report[representation]["leave_one_source_out_mean_across_sources"] = (
            mean_across_held_out_sources(cross_source[representation])
        )
        representations_report[representation][
            "leave_one_source_out_worst_source_macro_f1"
        ] = round(
            min(item["metrics"]["macro_f1"] for item in cross_source[representation].values()),
            6,
        )

    paired_bootstrap = None
    if selected_representation != BASELINE_REPRESENTATION:
        paired_bootstrap = paired_group_bootstrap(
            test_predictions[BASELINE_REPRESENTATION],
            test_predictions[selected_representation],
            test_truth,
            [row["split_group_id"] for row in test_rows],
        )
    baseline = representations_report[BASELINE_REPRESENTATION]
    selected = representations_report[selected_representation]
    baseline_validation_mean = baseline["validation_source_summary"][
        "unweighted_mean_macro_f1_across_sources"
    ]
    selected_validation_mean = selected["validation_source_summary"][
        "unweighted_mean_macro_f1_across_sources"
    ]
    baseline_loso_mean = baseline["leave_one_source_out_mean_across_sources"][
        "macro_f1"
    ]
    selected_loso_mean = selected["leave_one_source_out_mean_across_sources"][
        "macro_f1"
    ]
    improved_test_sources = sum(
        selected["test_by_source_dataset"][source]["macro_f1"]
        > baseline["test_by_source_dataset"][source]["macro_f1"]
        for source in baseline["test_by_source_dataset"]
    )
    promotion_checks = {
        "validation_selected_promotion_eligible_new_representation": (
            selected_representation != BASELINE_REPRESENTATION
        ),
        "validation_source_mean_macro_f1_improves_by_at_least_0_01": (
            selected_validation_mean - baseline_validation_mean >= 0.01
        ),
        "validation_worst_source_macro_f1_not_worse": selected[
            "validation_source_summary"
        ]["worst_source_macro_f1"]
        >= baseline["validation_source_summary"]["worst_source_macro_f1"],
        "internal_test_macro_f1_improves": selected["test"]["macro_f1"]
        > baseline["test"]["macro_f1"],
        "internal_test_source_mean_macro_f1_not_worse": selected[
            "test_source_summary"
        ]["unweighted_mean_macro_f1_across_sources"]
        >= baseline["test_source_summary"]["unweighted_mean_macro_f1_across_sources"],
        "internal_test_macro_f1_improves_on_at_least_two_sources": (
            improved_test_sources >= 2
        ),
        "leave_one_source_out_mean_macro_f1_improves_by_at_least_0_01": (
            selected_loso_mean - baseline_loso_mean >= 0.01
        ),
        "leave_one_source_out_worst_source_macro_f1_not_worse": selected[
            "leave_one_source_out_worst_source_macro_f1"
        ]
        >= baseline["leave_one_source_out_worst_source_macro_f1"],
        "paired_group_bootstrap_95_ci_lower_bound_gt_0": bool(
            paired_bootstrap and paired_bootstrap["ci_lower_bound_gt_0"]
        ),
    }
    qualifies_as_research_candidate = all(promotion_checks.values())

    vectorizer_contract = {
        "word": {
            "analyzer": "word",
            "ngram_range": [1, 2],
            "min_df": 2,
            "max_df": 0.995,
            "max_features": 100000,
            "sublinear_tf": True,
        },
        "char_wb": {
            "analyzer": "char_wb",
            "ngram_range": [3, 5],
            "min_df": 2,
            "max_df": 0.995,
            "max_features": CHAR_MAX_FEATURES,
            "sublinear_tf": True,
        },
        "char": {
            "analyzer": "char",
            "ngram_range": [3, 5],
            "min_df": 2,
            "max_df": 0.995,
            "max_features": CHAR_MAX_FEATURES,
            "sublinear_tf": True,
        },
        "combined_normalization": "L2 normalize the sparse word + char_wb horizontal stack",
    }
    report = {
        "analysis_id": ANALYSIS_ID,
        "run_at": run_at,
        "status": "FROZEN_RESEARCH_ABLATION_NOT_FOR_DEPLOYMENT",
        "label_semantics": LABEL_SEMANTICS,
        "data": {
            "input": str(args.input),
            "input_sha256": sha256_file(args.input),
            "partition_counts": {name: len(rows) for name, rows in splits.items()},
            "split_group_cross_partition_count": 0,
        },
        "feature_contract": {
            "predictive_input": ["text_content"],
            "source_dataset_in_feature_matrix": False,
            "source_dataset_allowed_uses": [
                "validation-only stratified metrics",
                "representation selection",
                "source-predictability and within-source shuffle diagnostics",
                "test stratified reporting",
                "leave-one-source-out evaluation",
            ],
            "vectorizers": vectorizer_contract,
            "raw_files_modified": False,
            "network_operations": 0,
        },
        "selection_policy": {
            "candidate_representations": list(REPRESENTATIONS),
            "promotion_eligible_representations": list(
                PROMOTION_ELIGIBLE_REPRESENTATIONS
            ),
            "char_3_5_role": "validation-only source-shortcut stress test",
            "selection_partitions": ["train", "validation"],
            "test_used_for_vectorizer_or_model_fitting": False,
            "test_used_for_hyperparameter_or_representation_selection": False,
            "all_downstream_classifier_hyperparameters_frozen": True,
            "frozen_classifier": {
                "C": FROZEN_C,
                "class_weight": FROZEN_CLASS_WEIGHT,
                "solver": "liblinear",
                "threshold": 0.5,
                "random_state": RANDOM_STATE,
            },
            "primary_metric": "unweighted mean of per-source validation Macro-F1",
            "tie_breakers": [
                "worst-source validation Macro-F1",
                "pooled validation Macro-F1",
                "simpler earlier representation",
            ],
            "selected_representation_on_validation": selected_representation,
            "representations_opened_on_internal_test": list(evaluated_representations),
        },
        "near_duplicate_diagnostic": {
            "normalized_template_partition_audit": template_partition_diagnostic,
            "method": (
                "maximum cosine similarity to any train row in train-fitted "
                "char_wb 3-5 TF-IDF space"
            ),
            "validation": similarity_summary(
                validation_char_similarities, validation_rows
            ),
            "test": similarity_summary(test_char_similarities, test_rows),
        },
        "representations": representations_report,
        "paired_test_group_bootstrap_selected_vs_word_baseline": paired_bootstrap,
        "decision": {
            "selected_representation_on_validation": selected_representation,
            "improved_internal_test_source_count": improved_test_sources,
            "promotion_checks": promotion_checks,
            "qualifies_as_internal_research_candidate": qualifies_as_research_candidate,
            "promote_to_primary_internal_baseline": False,
            "external_evidence_gate_required": True,
            "deployment_allowed": False,
            "policy": (
                "Passing every internal check creates only a research candidate. This repeatedly "
                "used internal test cannot promote a model; promotion requires an unopened external "
                "or evidence-backed curated evaluation set."
            ),
        },
        "prohibited_claims": [
            "Do not describe source label 1 as regulator-verified investment fraud.",
            "Do not describe scores as real-world scam probabilities.",
            "Do not interpret character fragments as causal scam evidence.",
            "Do not deploy this ablation for blocking, enforcement or financial decisions.",
        ],
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    results_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_predictions(
        predictions_path,
        test_rows,
        test_predictions,
        test_probabilities,
        evaluated_representations,
    )
    print(json.dumps({
        "analysis_id": ANALYSIS_ID,
        "input_sha256": report["data"]["input_sha256"],
        "selected_representation_on_validation": selected_representation,
        "decision": report["decision"],
        "baseline": {
            "validation": baseline["validation"],
            "validation_source_summary": baseline["validation_source_summary"],
            "test": baseline["test"],
            "leave_one_source_out_mean": baseline["leave_one_source_out_mean_across_sources"],
            "leave_one_source_out_worst_source_macro_f1": baseline[
                "leave_one_source_out_worst_source_macro_f1"
            ],
        },
        "selected": {
            "frozen_classifier": selected["frozen_classifier"],
            "validation": selected["validation"],
            "validation_source_summary": selected["validation_source_summary"],
            "test": selected["test"],
            "test_source_summary": selected["test_source_summary"],
            "leave_one_source_out_mean": selected["leave_one_source_out_mean_across_sources"],
            "leave_one_source_out_worst_source_macro_f1": selected[
                "leave_one_source_out_worst_source_macro_f1"
            ],
            "paired_group_bootstrap_vs_word_baseline": paired_bootstrap,
        },
        "outputs": {"results": str(results_path), "predictions": str(predictions_path)},
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
