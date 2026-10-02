"""Verify the frozen Wayback-language V2 diagnostic error analysis."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from mendeley_text_baseline_v2_common import sha256_file


ANALYSIS_ID = "ISI_TEXT_BASELINE_V2_WAYBACK_LANGUAGE_V2_ERROR_ANALYSIS"
EXPECTED_COUNTS = {
    "record_count": 38,
    "correct_count": 25,
    "error_count": 13,
    "false_positive_count": 9,
    "false_negative_count": 4,
    "predicted_label_1_count": 24,
    "predicted_label_0_count": 14,
    "errors_within_0_10_of_threshold": 8,
    "records_within_0_10_of_threshold": 17,
    "correct_records_within_0_10_of_threshold": 9,
}


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


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
    expected_status = "FROZEN_WAYBACK_LANGUAGE_V2_DIAGNOSTIC_COMPLETE_NO_TUNING"
    if registry.get("analysis_id") != ANALYSIS_ID:
        errors.append("Unexpected analysis ID")
    if registry.get("status") != expected_status:
        errors.append("Unexpected analysis status")
    entries = list(registry.get("implementation", [])) + list(registry.get("inputs", [])) + list(registry.get("outputs", []))
    paths: dict[str, Path] = {}
    for item in entries:
        role = str(item.get("role"))
        path = resolve(root, item.get("path", ""))
        actual = sha256_file(path) if path.is_file() else None
        paths[role] = path
        checked.append({"role": role, "path": str(path), "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"Artifact missing or changed: {role}")
    expected_output_roles = {"analysis_json", "diagnostics_jsonl", "error_queue_jsonl", "near_threshold_queue_jsonl", "report_markdown"}
    if {item.get("role") for item in registry.get("outputs", [])} != expected_output_roles:
        errors.append("Unexpected output roles")
    report = load_json(paths["analysis_json"]) if paths.get("analysis_json", Path()).is_file() else {}
    diagnostics = load_jsonl(paths["diagnostics_jsonl"]) if paths.get("diagnostics_jsonl", Path()).is_file() else []
    error_queue = load_jsonl(paths["error_queue_jsonl"]) if paths.get("error_queue_jsonl", Path()).is_file() else []
    near_queue = load_jsonl(paths["near_threshold_queue_jsonl"]) if paths.get("near_threshold_queue_jsonl", Path()).is_file() else []
    predictions = load_jsonl(paths["predictions_jsonl"]) if paths.get("predictions_jsonl", Path()).is_file() else []
    if report.get("analysis_id") != ANALYSIS_ID or report.get("status") != expected_status:
        errors.append("Analysis report identity or status mismatch")
    if report.get("counts") != EXPECTED_COUNTS:
        errors.append(f"Unexpected report counts: {report.get('counts')}")
    diagnostic_ids = [item.get("benchmark_record_id") for item in diagnostics]
    if len(diagnostics) != 38 or len(set(diagnostic_ids)) != 38:
        errors.append("Expected 38 unique diagnostics")
    predicted_by_id = {item.get("benchmark_record_id"): item for item in predictions}
    if set(diagnostic_ids) != set(predicted_by_id):
        errors.append("Diagnostics do not cover frozen predictions exactly")
    for item in diagnostics:
        record_id = item.get("benchmark_record_id")
        prediction = predicted_by_id.get(record_id, {})
        if (
            item.get("expected_source_label") != prediction.get("expected_source_label")
            or item.get("predicted_source_label") != prediction.get("predicted_source_label")
            or item.get("score_label_1") != prediction.get("score_label_1")
            or item.get("correct") != prediction.get("correct")
        ):
            errors.append(f"Diagnostic does not reproduce prediction: {record_id}")
        reconstructed = 1.0 / (1.0 + math.exp(-(float(item["model_intercept"]) + float(item["feature_contribution_sum"]))))
        if not math.isclose(reconstructed, float(item["score_label_1"]), rel_tol=0.0, abs_tol=1.1e-8):
            errors.append(f"Feature contributions do not reconstruct score: {record_id}")
        if item.get("near_threshold_within_0_10") != (float(item["distance_from_threshold"]) <= 0.10):
            errors.append(f"Near-threshold flag mismatch: {record_id}")
        if item.get("language_stratum") != "ENGLISH" or item.get("capture_stratum") != "WAYBACK_ARCHIVED_HOMEPAGE_HTML":
            errors.append(f"Stratum mismatch: {record_id}")
    expected_errors = {item["benchmark_record_id"] for item in diagnostics if not item["correct"]}
    expected_near = {item["benchmark_record_id"] for item in diagnostics if item["near_threshold_within_0_10"]}
    if {item.get("benchmark_record_id") for item in error_queue} != expected_errors or len(error_queue) != 13:
        errors.append("Error queue does not exactly match diagnostics")
    if {item.get("benchmark_record_id") for item in near_queue} != expected_near or len(near_queue) != 17:
        errors.append("Near-threshold queue does not exactly match diagnostics")
    if report.get("nearest_fit_source_profile") != {
        "all_records": {"cresci_stock_2018": 4, "phishing": 3, "spam_email": 31},
        "errors": {"cresci_stock_2018": 2, "phishing": 2, "spam_email": 9},
    }:
        errors.append("Unexpected nearest-fit source profile")
    strata = report.get("matched_strata_analysis", {})
    if strata.get("both_labels_share_capture_and_language_strata") is not True:
        errors.append("Matched stratum gate is false")
    gates = report.get("quality_gates", {})
    for key in (
        "frozen_model_hash_verified",
        "frozen_split_hash_verified",
        "stored_predictions_reproduced",
        "probabilities_reconstructed_from_feature_contributions",
        "all_38_records_diagnosed",
        "all_13_errors_queued",
        "both_labels_share_capture_and_language_strata",
        "model_fit_operations_zero",
        "threshold_changes_zero",
        "labels_changed_zero",
    ):
        if gates.get(key) is not True:
            errors.append(f"Quality gate is not true: {key}")
    access = report.get("data_access", {})
    if (
        access.get("external_records_transformed") != 38
        or access.get("frozen_fit_reference_rows_transformed_for_similarity_only") != 4754
        or access.get("frozen_internal_test_rows_loaded_or_transformed") != 0
        or access.get("auxiliary_rows_used") != 0
        or access.get("quarantine_rows_used") != 0
        or access.get("excluded_rows_used") != 0
    ):
        errors.append("Data-access firewall mismatch")
    safety = report.get("safety_contract", {})
    for key, expected in {
        "network_operations": 0,
        "candidate_domain_access_operations": 0,
        "model_fit_operations": 0,
        "threshold_changes": 0,
        "vectorizer_changes": 0,
        "labels_changed": 0,
        "benchmark_used_for_model_selection": False,
        "training_allowed": False,
        "deployment_allowed": False,
    }.items():
        if safety.get(key) != expected:
            errors.append(f"Safety contract mismatch: {key}")
    print(json.dumps({
        "analysis_id": registry.get("analysis_id"),
        "valid": not errors,
        "diagnostic_count": len(diagnostics),
        "error_count": len(error_queue),
        "near_threshold_count": len(near_queue),
        "errors": errors,
        "checked": checked,
    }, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
