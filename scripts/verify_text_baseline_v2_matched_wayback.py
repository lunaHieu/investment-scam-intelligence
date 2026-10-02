"""Verify the accepted matched-Wayback frozen-model evaluation and closed tuning gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mendeley_text_baseline_v2_common import sha256_file


EVALUATION_ID = "ISI_TEXT_BASELINE_V2_MATCHED_WAYBACK_V1"
EXPECTED_CONFUSION = {"tn": 5, "fp": 4, "fn": 2, "tp": 7}


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
    if registry.get("status") != "FROZEN_MODEL_MATCHED_EXTERNAL_DIAGNOSTIC_COMPLETE_NOT_FOR_DEPLOYMENT":
        errors.append("Unexpected evaluation status")
    entries = (
        list(registry.get("implementation", []))
        + list(registry.get("inputs", []))
        + list(registry.get("outputs", []))
    )
    for item in entries:
        path = resolve(root, item.get("path", ""))
        actual = sha256_file(path) if path.is_file() else None
        checked.append({"role": item.get("role"), "path": str(path), "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"Artifact missing or changed: {item.get('role')}")
    outputs = {item.get("role"): item for item in registry.get("outputs", [])}
    if set(outputs) != {"results_json", "predictions_jsonl", "report_markdown"}:
        errors.append("Unexpected output roles")
    report_path = resolve(root, outputs.get("results_json", {}).get("path", ""))
    predictions_path = resolve(root, outputs.get("predictions_jsonl", {}).get("path", ""))
    benchmark_entry = next(
        (item for item in registry.get("inputs", []) if item.get("role") == "matched_benchmark"), {}
    )
    benchmark_path = resolve(root, benchmark_entry.get("path", ""))
    report = load_json(report_path) if report_path.is_file() else {}
    benchmark = load_json(benchmark_path) if benchmark_path.is_file() else {}
    predictions = [
        json.loads(line)
        for line in predictions_path.read_text(encoding="utf-8").splitlines()
        if line
    ] if predictions_path.is_file() else []
    if report.get("evaluation_id") != EVALUATION_ID:
        errors.append("Report evaluation ID mismatch")
    if report.get("status") != registry.get("status"):
        errors.append("Report and registry statuses differ")
    ids = [item.get("benchmark_record_id") for item in predictions]
    if len(predictions) != 18 or len(set(ids)) != 18:
        errors.append("Expected 18 unique prediction rows")
    benchmark_records = {
        item.get("benchmark_record_id"): item for item in benchmark.get("records", [])
    }
    if set(ids) != set(benchmark_records):
        errors.append("Prediction coverage does not exactly match the benchmark")
    actual_confusion = {key: 0 for key in EXPECTED_CONFUSION}
    for item in predictions:
        record = benchmark_records.get(item.get("benchmark_record_id"), {})
        expected_truth = {"LEGITIMATE": 0, "CONFIRMED": 1}.get(record.get("ground_truth_status"))
        truth = item.get("expected_source_label")
        predicted = item.get("predicted_source_label")
        if (
            truth != expected_truth
            or item.get("ground_truth_status") != record.get("ground_truth_status")
            or item.get("artifact_text_sha256") != record.get("artifact", {}).get("text_sha256")
            or item.get("capture_stratum") != "WAYBACK_ARCHIVED_HOMEPAGE_HTML"
        ):
            errors.append(f"Prediction provenance mismatch: {item.get('benchmark_record_id')}")
        key = {(0, 0): "tn", (0, 1): "fp", (1, 0): "fn", (1, 1): "tp"}.get((truth, predicted))
        if key is None:
            errors.append(f"Invalid prediction values: {item.get('benchmark_record_id')}")
        else:
            actual_confusion[key] += 1
        if item.get("correct") != (truth == predicted):
            errors.append(f"Incorrect correctness flag: {item.get('benchmark_record_id')}")
    if actual_confusion != EXPECTED_CONFUSION:
        errors.append(f"Unexpected frozen confusion matrix: {actual_confusion}")
    if report.get("metrics", {}).get("confusion_matrix") != actual_confusion:
        errors.append("Report confusion matrix is not reproduced by predictions")
    expected_metrics = {
        "row_count": 18,
        "accuracy": 0.666667,
        "balanced_accuracy": 0.666667,
        "macro_f1": 0.6625,
        "roc_auc": 0.592593,
        "average_precision": 0.600812,
    }
    metrics = report.get("metrics", {})
    for key, value in expected_metrics.items():
        if metrics.get(key) != value:
            errors.append(f"Unexpected metric {key}: {metrics.get(key)}")
    data = report.get("data", {})
    if (
        data.get("record_count") != 18
        or data.get("confirmed_count") != 9
        or data.get("legitimate_count") != 9
        or data.get("capture_stratum") != "WAYBACK_ARCHIVED_HOMEPAGE_HTML"
        or data.get("independent_ai_second_review") is not True
        or data.get("independent_human_second_review") is not False
    ):
        errors.append("Evaluation data provenance mismatch")
    if report.get("prediction_profile", {}).get("error_count") != 6:
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
        "evidence_text_used_as_model_input": False,
        "training_allowed": False,
        "deployment_allowed": False,
    }.items():
        if safety.get(key) != expected:
            errors.append(f"Report safety contract mismatch: {key}")
    registry_safety = registry.get("safety_contract", {})
    for key, expected in {
        "network_operations": 0,
        "domain_access_allowed": False,
        "labels_created": 0,
        "model_fit_operations": 0,
        "threshold_changes": 0,
        "vectorizer_changes": 0,
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
        "errors": errors,
        "checked": checked,
    }, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
