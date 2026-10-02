"""Run the frozen V3 style-guard challenger without opening test or external data."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.multiclass import OneVsRestClassifier

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from mendeley_text_baseline_v2_common import (  # noqa: E402
    EXPECTED_SOURCES,
    EXPECTED_SPLIT_SHA256,
    RANDOM_STATE,
    binary_metrics,
    evaluate_by_source,
    fit_classifier,
    labels,
    make_classifier,
    make_vectorizer,
    read_selection_data,
    sha256_file,
    source_summary,
    texts,
)


PROTOCOL_ID = "MENDELEY_TEXT_CHALLENGER_V3_STYLE_GUARD_PROTOCOL"
SELECTION_ID = "MENDELEY_TEXT_CHALLENGER_V3_STYLE_GUARD_SELECTION"
EXPECTED_PROTOCOL_SHA256 = "e8b08eb24e0ab9432f2760efe535ba4fcc9b33e6c7182f12565da0426fa9a27e"
BASELINE_ID = "word_1_2"
CHALLENGER_ID = "word_1_2_english_stopwords"


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def canonical_digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_protocol(protocol_path: Path, split_path: Path, baseline_registry_path: Path) -> dict:
    if sha256_file(protocol_path) != EXPECTED_PROTOCOL_SHA256:
        raise ValueError("V3 protocol changed after it was frozen")
    protocol = load_json(protocol_path)
    if protocol.get("protocol_id") != PROTOCOL_ID:
        raise ValueError("Unexpected protocol ID")
    if protocol.get("status") != "FROZEN_BEFORE_DEVELOPMENT_AND_VALIDATION_TEST_EXTERNAL_UNOPENED":
        raise ValueError("Protocol is not frozen with test/external unopened")
    contract = protocol.get("data_contract", {})
    if sha256_file(split_path) != EXPECTED_SPLIT_SHA256:
        raise ValueError("Split hash mismatch")
    if contract.get("split_sha256") != EXPECTED_SPLIT_SHA256:
        raise ValueError("Protocol split hash mismatch")
    baseline_hash = sha256_file(baseline_registry_path)
    if baseline_hash != contract.get("baseline_registry_sha256"):
        raise ValueError("Baseline registry hash mismatch")
    design = protocol.get("development_design", {})
    if design.get("fold_count") != 4 or design.get("candidate_count") != 1:
        raise ValueError("Unexpected development design")
    if design.get("hyperparameter_search") is not False or design.get("threshold_search") is not False:
        raise ValueError("Search is prohibited")
    representations = protocol.get("representations", {})
    if representations.get("baseline", {}).get("id") != BASELINE_ID:
        raise ValueError("Unexpected baseline representation")
    if representations.get("single_challenger", {}).get("id") != CHALLENGER_ID:
        raise ValueError("Unexpected challenger representation")
    safety = protocol.get("safety_contract", {})
    required_zero = (
        "network_operations",
        "source_labels_changed",
        "existing_external_benchmark_scoring_operations",
        "internal_test_scoring_operations",
    )
    if any(safety.get(key) != 0 for key in required_zero):
        raise ValueError("Protocol opens a prohibited safety gate")
    return protocol


def make_stopword_vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(
        analyzer="word",
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.995,
        max_features=100_000,
        sublinear_tf=True,
        stop_words="english",
    )


def fit_binary(matrix, truth: np.ndarray) -> LogisticRegression:
    classifier = make_classifier({"C": 2.0, "class_weight": None})
    fit_classifier(classifier, matrix, truth)
    return classifier


def fit_source_classifier(matrix, rows) -> OneVsRestClassifier:
    targets = np.asarray([row["source_dataset"] for row in rows], dtype=object)
    estimator = LogisticRegression(
        C=2.0,
        class_weight=None,
        solver="liblinear",
        max_iter=2_000,
        random_state=RANDOM_STATE,
    )
    classifier = OneVsRestClassifier(estimator)
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        classifier.fit(matrix, targets)
    return classifier


def assign_development_folds(rows, *, fold_count: int, seed: str) -> dict[str, int]:
    members: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        members[row["split_group_id"]].append(row)
    strata: dict[tuple[str, str], list[str]] = defaultdict(list)
    for group_id, group_rows in members.items():
        sources = {row["source_dataset"] for row in group_rows}
        group_labels = {row["label"] for row in group_rows}
        if len(sources) != 1 or len(group_labels) != 1:
            raise ValueError(f"Development group mixes source or label: {group_id}")
        strata[(next(iter(sources)), next(iter(group_labels)))].append(group_id)
    mapping: dict[str, int] = {}
    for key in sorted(strata):
        ordered = sorted(
            strata[key],
            key=lambda group_id: hashlib.sha256(f"{seed}|{group_id}".encode("utf-8")).hexdigest(),
        )
        for index, group_id in enumerate(ordered):
            mapping[group_id] = index % fold_count
    if len(mapping) != len(members):
        raise ValueError("Not every development group received a fold")
    return mapping


def shuffled_labels_within_source(rows, *, seed: int) -> np.ndarray:
    result = labels(rows).copy()
    rng = np.random.default_rng(seed)
    for source in sorted({row["source_dataset"] for row in rows}):
        indices = np.asarray(
            [index for index, row in enumerate(rows) if row["source_dataset"] == source],
            dtype=np.int64,
        )
        values = result[indices].copy()
        rng.shuffle(values)
        result[indices] = values
    return result


def representation_report(rows, predictions: np.ndarray, probabilities: np.ndarray) -> dict:
    pooled = binary_metrics(labels(rows), predictions, probabilities)
    by_source = evaluate_by_source(rows, predictions, probabilities)
    return {
        "metrics": pooled,
        "by_source_dataset": by_source,
        "source_summary": source_summary(by_source),
    }


def source_metric(rows, predictions: np.ndarray) -> dict:
    truth = np.asarray([row["source_dataset"] for row in rows], dtype=object)
    majority = Counter(truth).most_common(1)[0][0]
    majority_predictions = np.full(len(truth), majority, dtype=object)
    return {
        "macro_f1": round(float(f1_score(truth, predictions, average="macro", zero_division=0)), 6),
        "majority_source_macro_f1": round(
            float(f1_score(truth, majority_predictions, average="macro", zero_division=0)), 6
        ),
        "source_dataset_used_as_diagnostic_target_only": True,
    }


def evaluate_fold(train_rows, evaluation_rows, vectorizer_factory, *, shuffle_seed: int) -> dict:
    vectorizer = vectorizer_factory()
    train_matrix = vectorizer.fit_transform(texts(train_rows)).tocsr()
    evaluation_matrix = vectorizer.transform(texts(evaluation_rows)).tocsr()
    classifier = fit_binary(train_matrix, labels(train_rows))
    probabilities = classifier.predict_proba(evaluation_matrix)[:, 1]
    predictions = (probabilities >= 0.5).astype(np.int64)
    source_classifier = fit_source_classifier(train_matrix, train_rows)
    source_predictions = source_classifier.predict(evaluation_matrix)
    shuffled_classifier = fit_binary(
        train_matrix, shuffled_labels_within_source(train_rows, seed=shuffle_seed)
    )
    shuffled_predictions = shuffled_classifier.predict(evaluation_matrix).astype(np.int64)
    return {
        "predictions": predictions,
        "probabilities": probabilities,
        "source_predictions": source_predictions,
        "shuffled_predictions": shuffled_predictions,
        "feature_count": int(train_matrix.shape[1]),
        "train_matrix_nnz": int(train_matrix.nnz),
        "evaluation_matrix_nnz": int(evaluation_matrix.nnz),
    }


def evaluate_confirmation(train_rows, validation_rows, vectorizer_factory) -> dict:
    vectorizer = vectorizer_factory()
    train_matrix = vectorizer.fit_transform(texts(train_rows)).tocsr()
    validation_matrix = vectorizer.transform(texts(validation_rows)).tocsr()
    classifier = fit_binary(train_matrix, labels(train_rows))
    probabilities = classifier.predict_proba(validation_matrix)[:, 1]
    predictions = (probabilities >= 0.5).astype(np.int64)
    source_classifier = fit_source_classifier(train_matrix, train_rows)
    source_predictions = source_classifier.predict(validation_matrix)
    return {
        "predictions": predictions,
        "probabilities": probabilities,
        "source_predictions": source_predictions,
        "feature_count": int(train_matrix.shape[1]),
        "train_matrix_nnz": int(train_matrix.nnz),
        "validation_matrix_nnz": int(validation_matrix.nnz),
    }


def macro_f1_from_confusion(values: np.ndarray) -> float:
    tn, fp, fn, tp = (float(value) for value in values)
    f1_0_denom = 2.0 * tn + fp + fn
    f1_1_denom = 2.0 * tp + fp + fn
    f1_0 = 0.0 if f1_0_denom == 0 else 2.0 * tn / f1_0_denom
    f1_1 = 0.0 if f1_1_denom == 0 else 2.0 * tp / f1_1_denom
    return (f1_0 + f1_1) / 2.0


def paired_group_bootstrap(reference, challenger, truth, groups, *, replicates: int, seed: int) -> dict:
    unique_groups = sorted(set(groups))
    positions = {group: index for index, group in enumerate(unique_groups)}
    reference_counts = np.zeros((len(unique_groups), 4), dtype=np.int64)
    challenger_counts = np.zeros((len(unique_groups), 4), dtype=np.int64)
    group_sizes = np.zeros(len(unique_groups), dtype=np.int64)
    confusion_index = {(0, 0): 0, (0, 1): 1, (1, 0): 2, (1, 1): 3}
    for actual, left, right, group in zip(truth, reference, challenger, groups):
        index = positions[group]
        group_sizes[index] += 1
        reference_counts[index, confusion_index[(int(actual), int(left))]] += 1
        challenger_counts[index, confusion_index[(int(actual), int(right))]] += 1
    rng = np.random.default_rng(seed)
    differences = np.empty(replicates, dtype=np.float64)
    for replicate in range(replicates):
        sampled = rng.integers(0, len(unique_groups), size=len(unique_groups))
        differences[replicate] = (
            macro_f1_from_confusion(challenger_counts[sampled].sum(axis=0))
            - macro_f1_from_confusion(reference_counts[sampled].sum(axis=0))
        )
    point = (
        macro_f1_from_confusion(challenger_counts.sum(axis=0))
        - macro_f1_from_confusion(reference_counts.sum(axis=0))
    )
    lower, upper = np.quantile(differences, [0.025, 0.975])
    return {
        "unit": "split_group_id",
        "cluster_count": len(unique_groups),
        "largest_cluster_rows": int(group_sizes.max()),
        "replicates": replicates,
        "seed": seed,
        "macro_f1_difference": round(float(point), 6),
        "difference_percentile_95_ci": [round(float(lower), 6), round(float(upper), 6)],
        "probability_challenger_better": round(float(np.mean(differences > 0.0)), 6),
    }


def comparison_values(baseline: dict, challenger: dict, source_delta: float) -> dict:
    baseline_by_source = baseline["by_source_dataset"]
    challenger_by_source = challenger["by_source_dataset"]
    per_source = {
        source: round(challenger_by_source[source]["macro_f1"] - baseline_by_source[source]["macro_f1"], 6)
        for source in sorted(baseline_by_source)
    }
    return {
        "source_mean_macro_f1_delta": round(
            challenger["source_summary"]["unweighted_mean_macro_f1_across_sources"]
            - baseline["source_summary"]["unweighted_mean_macro_f1_across_sources"], 6
        ),
        "worst_source_macro_f1_delta": round(
            challenger["source_summary"]["worst_source_macro_f1"]
            - baseline["source_summary"]["worst_source_macro_f1"], 6
        ),
        "pooled_macro_f1_delta": round(
            challenger["metrics"]["macro_f1"] - baseline["metrics"]["macro_f1"], 6
        ),
        "maximum_single_source_macro_f1_decline": round(
            max(0.0, max(-value for value in per_source.values())), 6
        ),
        "source_predictability_macro_f1_delta": round(source_delta, 6),
        "per_source_macro_f1_delta": per_source,
    }


def gate_comparison(values: dict, thresholds: dict, *, development: bool, bootstrap: dict | None = None,
                    shuffle_delta: float | None = None) -> dict:
    observed = dict(values)
    gates = {
        "source_mean_macro_f1_delta_minimum": values["source_mean_macro_f1_delta"]
        >= thresholds["source_mean_macro_f1_delta_minimum"],
        "worst_source_macro_f1_delta_minimum": values["worst_source_macro_f1_delta"]
        >= thresholds["worst_source_macro_f1_delta_minimum"],
        "pooled_macro_f1_delta_minimum": values["pooled_macro_f1_delta"]
        >= thresholds["pooled_macro_f1_delta_minimum"],
        "maximum_single_source_macro_f1_decline": values["maximum_single_source_macro_f1_decline"]
        <= thresholds["maximum_single_source_macro_f1_decline"],
        "source_predictability_macro_f1_delta_maximum": values["source_predictability_macro_f1_delta"]
        <= thresholds["source_predictability_macro_f1_delta_maximum"],
    }
    if development:
        observed["within_source_label_shuffle_macro_f1_delta"] = round(float(shuffle_delta), 6)
        gates["within_source_label_shuffle_macro_f1_delta_maximum"] = (
            observed["within_source_label_shuffle_macro_f1_delta"]
            <= thresholds["within_source_label_shuffle_macro_f1_delta_maximum"]
        )
    else:
        if bootstrap is None:
            raise ValueError("Validation gates require paired bootstrap")
        observed["paired_group_bootstrap_macro_f1_delta_ci_lower"] = bootstrap[
            "difference_percentile_95_ci"
        ][0]
        gates["paired_group_bootstrap_macro_f1_delta_ci_lower_minimum"] = (
            observed["paired_group_bootstrap_macro_f1_delta_ci_lower"]
            >= thresholds["paired_group_bootstrap_macro_f1_delta_ci_lower_minimum"]
        )
    return {
        "thresholds": thresholds,
        "observed": observed,
        "gates": gates,
        "all_gates_passed": all(gates.values()),
    }


def prepare_output_paths(output_dir: Path) -> dict[str, Path]:
    paths = {
        "selection": output_dir / "text_challenger_v3_validation_selection.json",
        "development_predictions": output_dir / "text_challenger_v3_development_oof_predictions.jsonl",
        "validation_predictions": output_dir / "text_challenger_v3_validation_predictions.jsonl",
    }
    for path in paths.values():
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite frozen output: {path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    return paths


def write_predictions(path: Path, rows, baseline, challenger, *, stage: str, fold_by_group=None) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for index, row in enumerate(rows):
            output = {
                "record_id": row["record_id"],
                "stage": stage,
                "partition": row["partition"],
                "split_group_id": row["split_group_id"],
                "source_dataset": row["source_dataset"],
                "source_label": int(row["label"]),
                "baseline_prediction": int(baseline["predictions"][index]),
                "baseline_score_label_1": round(float(baseline["probabilities"][index]), 10),
                "challenger_prediction": int(challenger["predictions"][index]),
                "challenger_score_label_1": round(float(challenger["probabilities"][index]), 10),
            }
            if fold_by_group is not None:
                output["development_fold"] = int(fold_by_group[row["split_group_id"]])
            handle.write(json.dumps(output, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--baseline-registry", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-at", required=True)
    args = parser.parse_args()
    protocol = validate_protocol(args.protocol, args.input, args.baseline_registry)
    output_paths = prepare_output_paths(args.output_dir)
    splits, access = read_selection_data(args.input)
    train_rows = splits["train"]
    validation_rows = splits["validation"]
    design = protocol["development_design"]
    fold_by_group = assign_development_folds(
        train_rows, fold_count=design["fold_count"], seed=design["fold_seed"]
    )
    factories = {BASELINE_ID: make_vectorizer, CHALLENGER_ID: make_stopword_vectorizer}
    oof = {
        name: {
            "predictions": np.empty(len(train_rows), dtype=np.int64),
            "probabilities": np.empty(len(train_rows), dtype=np.float64),
            "source_predictions": np.empty(len(train_rows), dtype=object),
            "shuffled_predictions": np.empty(len(train_rows), dtype=np.int64),
            "fold_diagnostics": [],
        }
        for name in factories
    }
    for fold in range(design["fold_count"]):
        fit_indices = [
            index for index, row in enumerate(train_rows)
            if fold_by_group[row["split_group_id"]] != fold
        ]
        eval_indices = [
            index for index, row in enumerate(train_rows)
            if fold_by_group[row["split_group_id"]] == fold
        ]
        fit_rows = [train_rows[index] for index in fit_indices]
        eval_rows = [train_rows[index] for index in eval_indices]
        if {row["source_dataset"] for row in fit_rows} != EXPECTED_SOURCES:
            raise ValueError(f"Fold {fold} fit lacks an expected source")
        if {row["source_dataset"] for row in eval_rows} != EXPECTED_SOURCES:
            raise ValueError(f"Fold {fold} evaluation lacks an expected source")
        for offset, (name, factory) in enumerate(factories.items()):
            result = evaluate_fold(
                fit_rows, eval_rows, factory, shuffle_seed=20261002 + fold * 10 + offset
            )
            for key in ("predictions", "probabilities", "source_predictions", "shuffled_predictions"):
                oof[name][key][eval_indices] = result[key]
            oof[name]["fold_diagnostics"].append({
                "fold": fold,
                "fit_rows": len(fit_rows),
                "evaluation_rows": len(eval_rows),
                "feature_count": result["feature_count"],
                "fit_matrix_nnz": result["train_matrix_nnz"],
                "evaluation_matrix_nnz": result["evaluation_matrix_nnz"],
            })
    development_reports = {}
    development_diagnostics = {}
    for name in factories:
        development_reports[name] = representation_report(
            train_rows, oof[name]["predictions"], oof[name]["probabilities"]
        )
        development_diagnostics[name] = {
            "source_predictability": source_metric(train_rows, oof[name]["source_predictions"]),
            "within_source_label_shuffle": {
                "macro_f1": round(
                    float(f1_score(labels(train_rows), oof[name]["shuffled_predictions"], average="macro", zero_division=0)),
                    6,
                ),
                "training_labels_shuffled_within_source": True,
            },
            "folds": oof[name]["fold_diagnostics"],
        }
    confirmation = {
        name: evaluate_confirmation(train_rows, validation_rows, factory)
        for name, factory in factories.items()
    }
    validation_reports = {
        name: representation_report(
            validation_rows, confirmation[name]["predictions"], confirmation[name]["probabilities"]
        )
        for name in factories
    }
    validation_diagnostics = {
        name: {
            "source_predictability": source_metric(
                validation_rows, confirmation[name]["source_predictions"]
            ),
            "feature_count": confirmation[name]["feature_count"],
            "train_matrix_nnz": confirmation[name]["train_matrix_nnz"],
            "validation_matrix_nnz": confirmation[name]["validation_matrix_nnz"],
        }
        for name in factories
    }
    bootstrap = paired_group_bootstrap(
        confirmation[BASELINE_ID]["predictions"],
        confirmation[CHALLENGER_ID]["predictions"],
        labels(validation_rows),
        [row["split_group_id"] for row in validation_rows],
        replicates=protocol["diagnostics"]["paired_bootstrap_replicates"],
        seed=protocol["diagnostics"]["paired_bootstrap_seed"],
    )
    dev_values = comparison_values(
        development_reports[BASELINE_ID],
        development_reports[CHALLENGER_ID],
        development_diagnostics[CHALLENGER_ID]["source_predictability"]["macro_f1"]
        - development_diagnostics[BASELINE_ID]["source_predictability"]["macro_f1"],
    )
    dev_decision = gate_comparison(
        dev_values,
        protocol["selection_policy"]["development_oof_gates"],
        development=True,
        shuffle_delta=(
            development_diagnostics[CHALLENGER_ID]["within_source_label_shuffle"]["macro_f1"]
            - development_diagnostics[BASELINE_ID]["within_source_label_shuffle"]["macro_f1"]
        ),
    )
    validation_values = comparison_values(
        validation_reports[BASELINE_ID],
        validation_reports[CHALLENGER_ID],
        validation_diagnostics[CHALLENGER_ID]["source_predictability"]["macro_f1"]
        - validation_diagnostics[BASELINE_ID]["source_predictability"]["macro_f1"],
    )
    validation_decision = gate_comparison(
        validation_values,
        protocol["selection_policy"]["validation_confirmation_gates"],
        development=False,
        bootstrap=bootstrap,
    )
    all_passed = dev_decision["all_gates_passed"] and validation_decision["all_gates_passed"]
    baseline_registry = load_json(args.baseline_registry)
    baseline_reproduced = (
        validation_reports[BASELINE_ID]["metrics"] == baseline_registry["metrics"]["validation"]
        and validation_reports[BASELINE_ID]["source_summary"]
        == baseline_registry["metrics"]["validation_source_summary"]
    )
    group_fold_counts = Counter(fold_by_group.values())
    row_fold_counts = Counter(fold_by_group[row["split_group_id"]] for row in train_rows)
    quality_gates = {
        "protocol_hash_verified": sha256_file(args.protocol) == EXPECTED_PROTOCOL_SHA256,
        "split_hash_verified": sha256_file(args.input) == EXPECTED_SPLIT_SHA256,
        "baseline_registry_hash_verified": sha256_file(args.baseline_registry)
        == protocol["data_contract"]["baseline_registry_sha256"],
        "baseline_validation_reproduced": baseline_reproduced,
        "train_rows_loaded_exact": len(train_rows) == 3916,
        "validation_rows_loaded_exact": len(validation_rows) == 838,
        "development_groups_assigned_once": len(fold_by_group) == 3783,
        "all_four_sources_present": {row["source_dataset"] for row in train_rows}
        == EXPECTED_SOURCES,
        "test_text_rows_loaded_zero": access["loaded_text_rows"]["test"] == 0,
        "test_text_transformed_zero": access["test_text_transformed"] == 0,
        "test_labels_used_zero": access["test_labels_used"] == 0,
        "auxiliary_and_quarantine_rows_used_zero": access["excluded_rows_used"] == 0,
        "single_challenger_only": set(factories) == {BASELINE_ID, CHALLENGER_ID},
        "external_benchmark_rows_loaded_zero": True,
        "model_artifact_created_false": True,
    }
    failed_quality = sorted(name for name, passed in quality_gates.items() if not passed)
    if failed_quality:
        raise ValueError("V3 quality gates failed: " + ", ".join(failed_quality))
    write_predictions(
        output_paths["development_predictions"], train_rows, oof[BASELINE_ID], oof[CHALLENGER_ID],
        stage="development_oof", fold_by_group=fold_by_group,
    )
    write_predictions(
        output_paths["validation_predictions"], validation_rows,
        confirmation[BASELINE_ID], confirmation[CHALLENGER_ID], stage="validation_confirmation",
    )
    stop_words = sorted(ENGLISH_STOP_WORDS)
    result = {
        "selection_id": SELECTION_ID,
        "run_at": args.run_at,
        "status": (
            "VALIDATION_RESEARCH_CANDIDATE_PASSED_TEST_EXTERNAL_UNOPENED"
            if all_passed else "VALIDATION_CHALLENGER_REJECTED_TEST_EXTERNAL_UNOPENED"
        ),
        "protocol": {"path": str(args.protocol), "sha256": sha256_file(args.protocol)},
        "data": {
            "input_path": str(args.input),
            "input_sha256": sha256_file(args.input),
            "train_row_count": len(train_rows),
            "validation_row_count": len(validation_rows),
            "development_group_count": len(fold_by_group),
            "development_group_count_by_fold": dict(sorted(group_fold_counts.items())),
            "development_row_count_by_fold": dict(sorted(row_fold_counts.items())),
            "data_access": access,
        },
        "representations": {
            BASELINE_ID: {"development_oof": development_reports[BASELINE_ID],
                          "development_diagnostics": development_diagnostics[BASELINE_ID],
                          "validation": validation_reports[BASELINE_ID],
                          "validation_diagnostics": validation_diagnostics[BASELINE_ID]},
            CHALLENGER_ID: {"development_oof": development_reports[CHALLENGER_ID],
                            "development_diagnostics": development_diagnostics[CHALLENGER_ID],
                            "validation": validation_reports[CHALLENGER_ID],
                            "validation_diagnostics": validation_diagnostics[CHALLENGER_ID],
                            "english_stop_words_count": len(stop_words),
                            "english_stop_words_sha256": canonical_digest(stop_words)},
        },
        "paired_group_bootstrap_validation": bootstrap,
        "decision": {
            "development_oof": dev_decision,
            "validation_confirmation": validation_decision,
            "all_required_gates_passed": all_passed,
            "selected_variant": CHALLENGER_ID if all_passed else BASELINE_ID,
            "internal_test_allowed": False,
            "existing_external_benchmark_allowed": False,
            "challenger_model_artifact_allowed": False,
        },
        "quality_gates": quality_gates,
        "safety_contract": {
            "network_operations": 0,
            "fit_scope": "development folds and full train only",
            "internal_test_rows_loaded": 0,
            "internal_test_rows_transformed": 0,
            "existing_external_benchmark_rows_loaded": 0,
            "existing_external_benchmark_rows_transformed": 0,
            "auxiliary_rows_used": 0,
            "quarantine_rows_used": 0,
            "manual_stop_word_changes": 0,
            "threshold_changes": 0,
            "model_artifact_created": False,
            "deployment_allowed": False,
        },
        "artifacts": {
            "development_oof_predictions": {
                "path": str(output_paths["development_predictions"]),
                "sha256": sha256_file(output_paths["development_predictions"]),
                "record_count": len(train_rows),
            },
            "validation_predictions": {
                "path": str(output_paths["validation_predictions"]),
                "sha256": sha256_file(output_paths["validation_predictions"]),
                "record_count": len(validation_rows),
            },
        },
    }
    output_paths["selection"].write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "selection": str(output_paths["selection"]),
        "selection_sha256": sha256_file(output_paths["selection"]),
        "development_predictions_sha256": sha256_file(output_paths["development_predictions"]),
        "validation_predictions_sha256": sha256_file(output_paths["validation_predictions"]),
        "status": result["status"],
        "development_decision": dev_decision,
        "validation_decision": validation_decision,
        "validation_bootstrap": bootstrap,
        "test_opened": False,
        "external_benchmark_opened": False,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
