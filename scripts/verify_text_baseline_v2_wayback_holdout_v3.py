"""Verify the frozen-model evaluation on Wayback holdout V3."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for value in (ROOT, SCRIPTS):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

from mendeley_text_baseline_v2_common import THRESHOLD, binary_metrics, sha256_file


EVALUATION_ID = "ISI_TEXT_BASELINE_V2_WAYBACK_HOLDOUT_V3"
EXPECTED_STATUS = "FROZEN_MODEL_WAYBACK_HOLDOUT_V3_DIAGNOSTIC_COMPLETE_NOT_FOR_DEPLOYMENT"
EXPECTED_CONFUSION = {"tn": 10, "fp": 5, "fn": 3, "tp": 12}
EXPECTED_METRICS = {
    "row_count": 30,
    "accuracy": 0.733333,
    "balanced_accuracy": 0.733333,
    "macro_f1": 0.732143,
    "roc_auc": 0.848889,
    "average_precision": 0.851282,
}
LABEL_MAP = {"LEGITIMATE": 0, "CONFIRMED": 1}


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def resolve(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    args = parser.parse_args()
    registry = load_json(args.registry)
    root = args.registry.resolve().parents[2]
    errors: list[str] = []
    checked = []
    if registry.get("analysis_id") != EVALUATION_ID:
        errors.append("Unexpected evaluation ID")
    if registry.get("status") != EXPECTED_STATUS:
        errors.append("Unexpected evaluation status")
    entries = list(registry.get("implementation", [])) + list(registry.get("inputs", [])) + list(registry.get("outputs", []))
    paths_by_role: dict[str, Path] = {}
    for item in entries:
        path = resolve(root, item.get("path", ""))
        actual = sha256_file(path) if path.is_file() else None
        role = str(item.get("role"))
        checked.append({"role": role, "path": str(path), "sha256": actual})
        if role in paths_by_role:
            errors.append(f"Duplicate role: {role}")
        paths_by_role[role] = path
        if actual != item.get("sha256"):
            errors.append(f"Artifact missing or changed: {role}")
    if {item.get("role") for item in registry.get("outputs", [])} != {"results_json", "predictions_jsonl", "report_markdown"}:
        errors.append("Unexpected output roles")
    required = {"model", "benchmark", "owner_acceptance", "results_json", "predictions_jsonl"}
    if not required.issubset(paths_by_role):
        errors.append("Registry is missing required roles")
    report = load_json(paths_by_role["results_json"]) if paths_by_role.get("results_json", Path()).is_file() else {}
    benchmark = load_json(paths_by_role["benchmark"]) if paths_by_role.get("benchmark", Path()).is_file() else {}
    predictions = [
        json.loads(line)
        for line in paths_by_role["predictions_jsonl"].read_text(encoding="utf-8").splitlines()
        if line
    ] if paths_by_role.get("predictions_jsonl", Path()).is_file() else []
    if report.get("evaluation_id") != EVALUATION_ID or report.get("status") != EXPECTED_STATUS:
        errors.append("Results report identity or status mismatch")
    ids = [item.get("benchmark_record_id") for item in predictions]
    if len(predictions) != 30 or len(set(ids)) != 30:
        errors.append("Expected 30 unique prediction rows")
    benchmark_records = {item.get("benchmark_record_id"): item for item in benchmark.get("records", [])}
    if set(ids) != set(benchmark_records):
        errors.append("Prediction coverage does not exactly match benchmark")
    actual_confusion = {key: 0 for key in EXPECTED_CONFUSION}
    for prediction in predictions:
        record = benchmark_records.get(prediction.get("benchmark_record_id"), {})
        truth = LABEL_MAP.get(record.get("ground_truth_status"))
        predicted = prediction.get("predicted_source_label")
        if (
            prediction.get("expected_source_label") != truth
            or prediction.get("ground_truth_status") != record.get("ground_truth_status")
            or prediction.get("artifact_text_sha256") != record.get("artifact", {}).get("text_sha256")
            or prediction.get("language_stratum") != "ENGLISH"
            or prediction.get("capture_stratum") != "WAYBACK_ARCHIVED_HOMEPAGE_HTML"
        ):
            errors.append(f"Prediction provenance mismatch: {prediction.get('benchmark_record_id')}")
        key = {(0, 0): "tn", (0, 1): "fp", (1, 0): "fn", (1, 1): "tp"}.get((truth, predicted))
        if key is None:
            errors.append(f"Invalid prediction values: {prediction.get('benchmark_record_id')}")
        else:
            actual_confusion[key] += 1
        if prediction.get("correct") != (truth == predicted):
            errors.append(f"Incorrect correctness flag: {prediction.get('benchmark_record_id')}")
    if actual_confusion != EXPECTED_CONFUSION:
        errors.append(f"Unexpected frozen confusion matrix: {actual_confusion}")
    metrics = report.get("metrics", {})
    for key, value in EXPECTED_METRICS.items():
        if metrics.get(key) != value:
            errors.append(f"Unexpected metric {key}: {metrics.get(key)}")
    if metrics.get("confusion_matrix") != actual_confusion:
        errors.append("Report confusion matrix is not reproduced by predictions")
    if paths_by_role.get("model", Path()).is_file() and benchmark_records and predictions:
        bundle = joblib.load(paths_by_role["model"])
        ordered_records = [benchmark_records[item["benchmark_record_id"]] for item in predictions]
        texts = [record["artifact"]["visible_text"] for record in ordered_records]
        truth = np.asarray([LABEL_MAP[record["ground_truth_status"]] for record in ordered_records], dtype=np.int64)
        matrix = bundle["vectorizer"].transform(texts).tocsr()
        probabilities = bundle["classifier"].predict_proba(matrix)[:, 1]
        predicted = (probabilities >= THRESHOLD).astype(np.int64)
        recomputed = binary_metrics(truth, predicted, probabilities)
        if recomputed != metrics:
            errors.append("Metrics are not reproduced from the frozen model and benchmark text")
        for item, probability, label in zip(predictions, probabilities, predicted):
            if item.get("score_label_1") != round(float(probability), 10) or item.get("predicted_source_label") != int(label):
                errors.append(f"Frozen score mismatch: {item.get('benchmark_record_id')}")
    data = report.get("data", {})
    if (
        data.get("record_count") != 30
        or data.get("confirmed_count") != 15
        or data.get("legitimate_count") != 15
        or data.get("language_stratum") != "ENGLISH"
        or data.get("capture_stratum") != "WAYBACK_ARCHIVED_HOMEPAGE_HTML"
        or data.get("independent_ai_second_review") is not True
        or data.get("independent_human_second_review") is not False
    ):
        errors.append("Evaluation data provenance mismatch")
    if report.get("prediction_profile", {}).get("error_count") != 8:
        errors.append("Unexpected error count")
    interpretation = report.get("interpretation", {})
    if (
        interpretation.get("real_world_scam_probability") is not False
        or interpretation.get("benchmark_may_be_used_for_tuning") is not False
        or interpretation.get("evaluation_supports_deployment_claim") is not False
    ):
        errors.append("Interpretation gate is open")
    safety = report.get("safety_contract", {})
    for key, expected in {
        "network_operations": 0,
        "model_fit_operations": 0,
        "threshold_changes": 0,
        "vectorizer_changes": 0,
        "warning_or_registry_evidence_used_as_model_input": False,
        "review_rationale_used_as_model_input": False,
        "source_text_modified": False,
        "training_allowed": False,
        "deployment_allowed": False,
    }.items():
        if safety.get(key) != expected:
            errors.append(f"Results safety contract mismatch: {key}")
    registry_safety = registry.get("safety_contract", {})
    for key, expected in {
        "network_operations": 0,
        "candidate_domain_access_operations": 0,
        "model_fit_operations": 0,
        "threshold_changes": 0,
        "vectorizer_changes": 0,
        "benchmark_used_for_tuning": False,
        "training_allowed": False,
        "deployment_allowed": False,
    }.items():
        if registry_safety.get(key) != expected:
            errors.append(f"Registry safety contract mismatch: {key}")
    print(json.dumps({
        "analysis_id": registry.get("analysis_id"),
        "valid": not errors,
        "prediction_count": len(predictions),
        "confusion_matrix": actual_confusion,
        "metrics": {key: metrics.get(key) for key in EXPECTED_METRICS},
        "errors": errors,
        "checked": checked,
    }, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
