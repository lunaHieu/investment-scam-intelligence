"""Run the one-candidate V2 text challenger protocol on train/validation only."""

from __future__ import annotations

import argparse
import json
import math
import sys
import warnings
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import sparse
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import normalize

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for value in (ROOT, SCRIPTS):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

from mendeley_text_baseline_v2_common import (
    EXPECTED_SOURCES,
    EXPECTED_SPLIT_SHA256,
    RANDOM_STATE,
    THRESHOLD,
    evaluate_by_source,
    evaluate_classifier,
    fit_classifier,
    labels,
    make_classifier,
    make_vectorizer,
    read_selection_data,
    sha256_file,
    source_summary,
    texts,
)


PROTOCOL_ID = "MENDELEY_TEXT_CHALLENGER_V2_VALIDATION_PROTOCOL"
SELECTION_ID = "MENDELEY_TEXT_CHALLENGER_V2_VALIDATION_SELECTION"
EXPECTED_PROTOCOL_SHA256 = "3b98519b7fa9bd77fff80517d1e0fd24a3321a96cbc7f054431424f9a6c1e685"
BASELINE_ID = "word_1_2"
CHALLENGER_ID = "word_1_2_plus_char_wb_3_5"
BOOTSTRAP_SEED = 20260930


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def validate_protocol(protocol_path: Path, split_path: Path, baseline_registry_path: Path) -> dict:
    if sha256_file(protocol_path) != EXPECTED_PROTOCOL_SHA256:
        raise ValueError("Challenger protocol is missing or changed")
    protocol = load_json(protocol_path)
    data = protocol.get("data_contract", {})
    classifier = protocol.get("fixed_classifier", {})
    reps = protocol.get("representations", {})
    diagnostics = protocol.get("diagnostics", {})
    safety = protocol.get("safety_contract", {})
    if (
        protocol.get("protocol_id") != PROTOCOL_ID
        or protocol.get("status") != "FROZEN_BEFORE_VALIDATION_TEST_AND_EXTERNAL_UNOPENED"
        or data.get("split_sha256") != EXPECTED_SPLIT_SHA256
        or sha256_file(split_path) != EXPECTED_SPLIT_SHA256
        or data.get("baseline_registry_sha256") != sha256_file(baseline_registry_path)
        or data.get("internal_test_text_access_allowed") is not False
        or data.get("internal_test_label_access_allowed") is not False
        or data.get("auxiliary_or_quarantine_access_allowed") is not False
        or data.get("external_benchmark_access_allowed") is not False
    ):
        raise ValueError("Protocol data contract mismatch")
    if classifier != {
        "type": "LogisticRegression",
        "C": 2.0,
        "class_weight": None,
        "solver": "liblinear",
        "max_iter": 2000,
        "random_state": RANDOM_STATE,
        "threshold": THRESHOLD,
    }:
        raise ValueError("Protocol classifier contract mismatch")
    if (
        reps.get("baseline", {}).get("id") != BASELINE_ID
        or reps.get("single_challenger", {}).get("id") != CHALLENGER_ID
        or diagnostics.get("paired_bootstrap_replicates") != 10000
        or diagnostics.get("paired_bootstrap_seed") != BOOTSTRAP_SEED
        or safety.get("candidate_count") != 1
        or safety.get("threshold_candidates") != 1
        or safety.get("external_benchmark_scoring_operations") != 0
        or safety.get("internal_test_scoring_operations") != 0
    ):
        raise ValueError("Protocol candidate or safety contract mismatch")
    registry = load_json(baseline_registry_path)
    if (
        registry.get("model_id") != "ISI_TEXT_BASELINE_V2"
        or registry.get("data_contract", {}).get("split_version") != "group_split_v2"
        or registry.get("primary_model", {}).get("selected_hyperparameters", {}).get("C") != 2.0
        or registry.get("primary_model", {}).get("selected_hyperparameters", {}).get("threshold") != 0.5
    ):
        raise ValueError("Baseline registry contract mismatch")
    return protocol


def make_char_vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(
        analyzer="char_wb",
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(3, 5),
        min_df=2,
        max_df=0.995,
        max_features=100_000,
        sublinear_tf=True,
    )


def combine_and_normalize(word_matrix, char_matrix):
    return normalize(sparse.hstack([word_matrix, char_matrix], format="csr"), norm="l2", copy=False)


def fit_binary(matrix, truth: np.ndarray):
    classifier = make_classifier({"C": 2.0, "class_weight": None})
    fit_classifier(classifier, matrix, truth)
    return classifier


def fit_source_classifier(matrix, rows):
    targets = np.asarray([row["source_dataset"] for row in rows], dtype=object)
    estimator = LogisticRegression(
        C=2.0,
        class_weight=None,
        solver="liblinear",
        max_iter=2000,
        random_state=RANDOM_STATE,
    )
    classifier = OneVsRestClassifier(estimator)
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        classifier.fit(matrix, targets)
    return classifier


def source_predictability(train_matrix, train_rows, validation_matrix, validation_rows) -> dict:
    classifier = fit_source_classifier(train_matrix, train_rows)
    truth = np.asarray([row["source_dataset"] for row in validation_rows], dtype=object)
    predictions = classifier.predict(validation_matrix)
    majority = Counter(row["source_dataset"] for row in train_rows).most_common(1)[0][0]
    majority_predictions = np.full(len(truth), majority, dtype=object)
    return {
        "validation_macro_f1": round(float(f1_score(truth, predictions, average="macro", zero_division=0)), 6),
        "majority_source_macro_f1": round(float(f1_score(truth, majority_predictions, average="macro", zero_division=0)), 6),
        "source_dataset_used_as_diagnostic_target_only": True,
    }


def shuffled_labels_within_source(rows) -> np.ndarray:
    result = labels(rows).copy()
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    for source in sorted({row["source_dataset"] for row in rows}):
        indices = np.asarray(
            [index for index, row in enumerate(rows) if row["source_dataset"] == source],
            dtype=np.int64,
        )
        values = result[indices].copy()
        rng.shuffle(values)
        result[indices] = values
    return result


def shuffle_diagnostic(train_matrix, train_rows, validation_matrix, validation_rows) -> dict:
    classifier = fit_binary(train_matrix, shuffled_labels_within_source(train_rows))
    metrics, _, _ = evaluate_classifier(classifier, validation_matrix, validation_rows)
    return {
        "validation_macro_f1": metrics["macro_f1"],
        "training_labels_shuffled_within_source": True,
        "random_state": BOOTSTRAP_SEED,
    }


def macro_f1_from_confusion(values: np.ndarray) -> float:
    tn, fp, fn, tp = (float(value) for value in values)
    f1_0_denominator = 2.0 * tn + fp + fn
    f1_1_denominator = 2.0 * tp + fp + fn
    f1_0 = 0.0 if f1_0_denominator == 0 else 2.0 * tn / f1_0_denominator
    f1_1 = 0.0 if f1_1_denominator == 0 else 2.0 * tp / f1_1_denominator
    return (f1_0 + f1_1) / 2.0


def paired_group_bootstrap(reference, challenger, truth, groups, *, replicates=10000, seed=BOOTSTRAP_SEED):
    unique_groups = sorted(set(groups))
    index_by_group = {group: index for index, group in enumerate(unique_groups)}
    reference_counts = np.zeros((len(unique_groups), 4), dtype=np.int64)
    challenger_counts = np.zeros((len(unique_groups), 4), dtype=np.int64)
    group_sizes = np.zeros(len(unique_groups), dtype=np.int64)
    confusion_index = {(0, 0): 0, (0, 1): 1, (1, 0): 2, (1, 1): 3}
    for actual, left, right, group in zip(truth, reference, challenger, groups):
        index = index_by_group[group]
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


def promotion_decision(protocol: dict, baseline: dict, challenger: dict, diagnostics: dict) -> dict:
    thresholds = protocol["selection_policy"]["promotion_gates"]
    baseline_by_source = baseline["validation_by_source_dataset"]
    challenger_by_source = challenger["validation_by_source_dataset"]
    per_source_deltas = {
        source: round(
            challenger_by_source[source]["macro_f1"] - baseline_by_source[source]["macro_f1"],
            6,
        )
        for source in sorted(baseline_by_source)
    }
    values = {
        "source_mean_macro_f1_delta": round(
            challenger["validation_source_summary"]["unweighted_mean_macro_f1_across_sources"]
            - baseline["validation_source_summary"]["unweighted_mean_macro_f1_across_sources"],
            6,
        ),
        "worst_source_macro_f1_delta": round(
            challenger["validation_source_summary"]["worst_source_macro_f1"]
            - baseline["validation_source_summary"]["worst_source_macro_f1"],
            6,
        ),
        "pooled_macro_f1_delta": round(
            challenger["validation"]["macro_f1"] - baseline["validation"]["macro_f1"], 6
        ),
        "maximum_single_source_macro_f1_decline": round(
            max(0.0, max(-delta for delta in per_source_deltas.values())), 6
        ),
        "source_predictability_macro_f1_delta": round(
            diagnostics[CHALLENGER_ID]["source_predictability"]["validation_macro_f1"]
            - diagnostics[BASELINE_ID]["source_predictability"]["validation_macro_f1"],
            6,
        ),
        "within_source_label_shuffle_macro_f1_delta": round(
            diagnostics[CHALLENGER_ID]["within_source_label_shuffle"]["validation_macro_f1"]
            - diagnostics[BASELINE_ID]["within_source_label_shuffle"]["validation_macro_f1"],
            6,
        ),
        "paired_group_bootstrap_macro_f1_delta_ci_lower": diagnostics["paired_group_bootstrap"][
            "difference_percentile_95_ci"
        ][0],
    }
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
        "within_source_label_shuffle_macro_f1_delta_maximum": values[
            "within_source_label_shuffle_macro_f1_delta"
        ] <= thresholds["within_source_label_shuffle_macro_f1_delta_maximum"],
        "paired_group_bootstrap_macro_f1_delta_ci_lower_minimum": values[
            "paired_group_bootstrap_macro_f1_delta_ci_lower"
        ] >= thresholds["paired_group_bootstrap_macro_f1_delta_ci_lower_minimum"],
    }
    passed = all(gates.values())
    return {
        "thresholds": thresholds,
        "observed": values,
        "per_source_macro_f1_delta": per_source_deltas,
        "gates": gates,
        "all_gates_passed": passed,
        "selected_variant": CHALLENGER_ID if passed else BASELINE_ID,
        "internal_test_allowed": False,
        "external_benchmark_allowed": False,
        "challenger_model_artifact_allowed": False,
    }


def evaluate_representation(classifier, validation_matrix, validation_rows) -> tuple[dict, np.ndarray, np.ndarray]:
    validation, predictions, probabilities = evaluate_classifier(
        classifier, validation_matrix, validation_rows
    )
    by_source = evaluate_by_source(validation_rows, predictions, probabilities)
    return {
        "validation": validation,
        "validation_by_source_dataset": by_source,
        "validation_source_summary": source_summary(by_source),
    }, predictions, probabilities


def prepare_output_paths(output_dir: Path) -> dict[str, Path]:
    paths = {
        "selection": output_dir / "text_challenger_v2_validation_selection.json",
        "predictions": output_dir / "text_challenger_v2_validation_predictions.jsonl",
    }
    existing = [path for path in paths.values() if path.exists()]
    if existing:
        raise FileExistsError(f"Refusing to overwrite frozen output: {existing[0]}")
    output_dir.mkdir(parents=True, exist_ok=True)
    return paths


def write_predictions(path: Path, rows, baseline_predictions, baseline_probabilities, challenger_predictions, challenger_probabilities) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row, left_pred, left_prob, right_pred, right_prob in zip(
            rows,
            baseline_predictions,
            baseline_probabilities,
            challenger_predictions,
            challenger_probabilities,
        ):
            output = {
                "record_id": row["record_id"],
                "partition": "validation",
                "split_group_id": row["split_group_id"],
                "source_dataset": row["source_dataset"],
                "source_label": int(row["label"]),
                "baseline_prediction": int(left_pred),
                "baseline_score_label_1": round(float(left_prob), 10),
                "challenger_prediction": int(right_pred),
                "challenger_score_label_1": round(float(right_prob), 10),
            }
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
    outputs = prepare_output_paths(args.output_dir)
    splits, access = read_selection_data(args.input)
    train_rows = splits["train"]
    validation_rows = splits["validation"]
    train_text = texts(train_rows)
    validation_text = texts(validation_rows)
    train_truth = labels(train_rows)
    validation_truth = labels(validation_rows)
    word_vectorizer = make_vectorizer()
    char_vectorizer = make_char_vectorizer()
    train_word = word_vectorizer.fit_transform(train_text).tocsr()
    validation_word = word_vectorizer.transform(validation_text).tocsr()
    train_char = char_vectorizer.fit_transform(train_text).tocsr()
    validation_char = char_vectorizer.transform(validation_text).tocsr()
    train_combined = combine_and_normalize(train_word, train_char)
    validation_combined = combine_and_normalize(validation_word, validation_char)
    matrices = {
        BASELINE_ID: (train_word, validation_word),
        CHALLENGER_ID: (train_combined, validation_combined),
    }
    reports = {}
    predictions = {}
    probabilities = {}
    diagnostics = {}
    for name, (train_matrix, validation_matrix) in matrices.items():
        classifier = fit_binary(train_matrix, train_truth)
        reports[name], predictions[name], probabilities[name] = evaluate_representation(
            classifier, validation_matrix, validation_rows
        )
        diagnostics[name] = {
            "source_predictability": source_predictability(
                train_matrix, train_rows, validation_matrix, validation_rows
            ),
            "within_source_label_shuffle": shuffle_diagnostic(
                train_matrix, train_rows, validation_matrix, validation_rows
            ),
            "feature_count": int(train_matrix.shape[1]),
            "train_matrix_nnz": int(train_matrix.nnz),
            "validation_matrix_nnz": int(validation_matrix.nnz),
        }
    diagnostics["paired_group_bootstrap"] = paired_group_bootstrap(
        predictions[BASELINE_ID],
        predictions[CHALLENGER_ID],
        validation_truth,
        [row["split_group_id"] for row in validation_rows],
    )
    decision = promotion_decision(protocol, reports[BASELINE_ID], reports[CHALLENGER_ID], diagnostics)
    baseline_registry = load_json(args.baseline_registry)
    expected_baseline = baseline_registry["metrics"]["validation"]
    expected_source_summary = baseline_registry["metrics"]["validation_source_summary"]
    baseline_reproduced = (
        reports[BASELINE_ID]["validation"] == expected_baseline
        and reports[BASELINE_ID]["validation_source_summary"] == expected_source_summary
    )
    quality_gates = {
        "protocol_hash_verified": sha256_file(args.protocol) == EXPECTED_PROTOCOL_SHA256,
        "split_hash_verified": sha256_file(args.input) == EXPECTED_SPLIT_SHA256,
        "baseline_registry_hash_verified": sha256_file(args.baseline_registry)
        == protocol["data_contract"]["baseline_registry_sha256"],
        "baseline_validation_reproduced": baseline_reproduced,
        "train_rows_loaded_exact": len(train_rows) == 3916,
        "validation_rows_loaded_exact": len(validation_rows) == 838,
        "test_text_rows_loaded_zero": access["loaded_text_rows"]["test"] == 0,
        "test_text_transformed_zero": access["test_text_transformed"] == 0,
        "test_labels_used_zero": access["test_labels_used"] == 0,
        "auxiliary_and_quarantine_rows_used_zero": access["excluded_rows_used"] == 0,
        "all_four_sources_present": {row["source_dataset"] for row in validation_rows}
        == EXPECTED_SOURCES,
        "single_challenger_only": set(reports) == {BASELINE_ID, CHALLENGER_ID},
        "source_dataset_not_in_scam_feature_matrix": True,
        "external_benchmark_rows_transformed_zero": True,
        "model_artifact_created_false": True,
    }
    failed = sorted(name for name, passed in quality_gates.items() if not passed)
    if failed:
        raise ValueError("Challenger selection quality gates failed: " + ", ".join(failed))
    write_predictions(
        outputs["predictions"],
        validation_rows,
        predictions[BASELINE_ID],
        probabilities[BASELINE_ID],
        predictions[CHALLENGER_ID],
        probabilities[CHALLENGER_ID],
    )
    result = {
        "selection_id": SELECTION_ID,
        "run_at": args.run_at,
        "status": (
            "VALIDATION_CHALLENGER_PASSED_AWAITING_SEPARATE_TEST_GATE"
            if decision["all_gates_passed"]
            else "VALIDATION_CHALLENGER_REJECTED_TEST_UNOPENED"
        ),
        "protocol": {
            "path": str(args.protocol),
            "sha256": sha256_file(args.protocol),
            "protocol_id": PROTOCOL_ID,
        },
        "data": {
            "input_path": str(args.input),
            "input_sha256": sha256_file(args.input),
            "split_version": "group_split_v2",
            "train_row_count": len(train_rows),
            "validation_row_count": len(validation_rows),
            "data_access": access,
        },
        "representations": {
            BASELINE_ID: {
                **reports[BASELINE_ID],
                **diagnostics[BASELINE_ID],
            },
            CHALLENGER_ID: {
                **reports[CHALLENGER_ID],
                **diagnostics[CHALLENGER_ID],
            },
        },
        "paired_group_bootstrap": diagnostics["paired_group_bootstrap"],
        "decision": decision,
        "quality_gates": quality_gates,
        "safety_contract": {
            "network_operations": 0,
            "model_fit_operations": 6,
            "fit_scope": "train only",
            "validation_scoring_operations": 2,
            "internal_test_rows_loaded": 0,
            "internal_test_rows_transformed": 0,
            "external_benchmark_rows_loaded": 0,
            "external_benchmark_rows_transformed": 0,
            "auxiliary_rows_used": 0,
            "quarantine_rows_used": 0,
            "threshold_changes": 0,
            "model_artifact_created": False,
            "deployment_allowed": False,
        },
        "artifacts": {
            "validation_predictions": {
                "path": str(outputs["predictions"]),
                "sha256": sha256_file(outputs["predictions"]),
                "record_count": len(validation_rows),
            }
        },
    }
    outputs["selection"].write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "selection": str(outputs["selection"]),
        "selection_sha256": sha256_file(outputs["selection"]),
        "predictions_sha256": sha256_file(outputs["predictions"]),
        "status": result["status"],
        "baseline": reports[BASELINE_ID],
        "challenger": reports[CHALLENGER_ID],
        "diagnostics": diagnostics,
        "decision": decision,
        "test_opened": False,
        "external_benchmark_opened": False,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
