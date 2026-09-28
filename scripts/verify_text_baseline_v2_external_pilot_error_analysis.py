"""Verify the frozen external-pilot error-analysis artifacts and closed tuning gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from validate_external_text_intake import sha256_file


ANALYSIS_ID = "ISI_TEXT_BASELINE_V2_EXTERNAL_PILOT_ERROR_ANALYSIS_V1"
STATUS = "FROZEN_EXTERNAL_DIAGNOSTIC_COMPLETE_NO_TUNING"
EXPECTED_OUTPUT_ROLES = {
    "analysis_json",
    "diagnostics_jsonl",
    "error_queue_jsonl",
    "report_markdown",
}


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict[str, object]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line:
            raise ValueError(f"Blank JSONL line: {line_number}")
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"JSONL line is not an object: {line_number}")
        rows.append(value)
    return rows


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

    if registry.get("analysis_id") != ANALYSIS_ID:
        errors.append("Unexpected analysis ID")
    if registry.get("status") != STATUS:
        errors.append("Unexpected analysis status")
    if registry.get("source_id") != "mendeley_investment_deceptive_2026":
        errors.append("Unexpected source ID")

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
    if set(outputs) != EXPECTED_OUTPUT_ROLES:
        errors.append("Unexpected output roles")
    report_path = resolve(root, outputs.get("analysis_json", {}).get("path", ""))
    diagnostics_path = resolve(root, outputs.get("diagnostics_jsonl", {}).get("path", ""))
    error_queue_path = resolve(root, outputs.get("error_queue_jsonl", {}).get("path", ""))

    report = load_json(report_path) if report_path.is_file() else {}
    diagnostics = load_jsonl(diagnostics_path) if diagnostics_path.is_file() else []
    queue = load_jsonl(error_queue_path) if error_queue_path.is_file() else []
    if report.get("analysis_id") != ANALYSIS_ID or report.get("status") != STATUS:
        errors.append("Report ID/status mismatch")

    diagnostic_ids = [item.get("case_id") for item in diagnostics]
    queue_ids = [item.get("case_id") for item in queue]
    if len(diagnostics) != 21 or len(set(diagnostic_ids)) != 21:
        errors.append("Expected 21 unique diagnostic rows")
    if len(queue) != 8 or len(set(queue_ids)) != 8:
        errors.append("Expected 8 unique error rows")
    calculated_error_ids = {
        item.get("case_id") for item in diagnostics if item.get("correct") is False
    }
    if calculated_error_ids != set(queue_ids):
        errors.append("Error queue does not equal the incorrect diagnostic subset")
    if any(item.get("correct") is not False for item in queue):
        errors.append("Error queue contains a correct prediction")

    actual_counts = {
        "record_count": len(diagnostics),
        "correct_count": sum(item.get("correct") is True for item in diagnostics),
        "error_count": sum(item.get("correct") is False for item in diagnostics),
        "false_positive_count": sum(item.get("error_type") == "false_positive" for item in diagnostics),
        "false_negative_count": sum(item.get("error_type") == "false_negative" for item in diagnostics),
        "predicted_label_1_count": sum(item.get("predicted_source_label") == 1 for item in diagnostics),
        "predicted_label_0_count": sum(item.get("predicted_source_label") == 0 for item in diagnostics),
        "errors_within_0_10_of_threshold": sum(
            item.get("correct") is False and float(item.get("distance_from_threshold", 1.0)) <= 0.10
            for item in diagnostics
        ),
    }
    if report.get("counts") != actual_counts:
        errors.append("Report counts do not reproduce from diagnostics")
    expected_counts = {
        "record_count": 21,
        "correct_count": 13,
        "error_count": 8,
        "false_positive_count": 6,
        "false_negative_count": 2,
        "predicted_label_1_count": 14,
        "predicted_label_0_count": 7,
        "errors_within_0_10_of_threshold": 4,
    }
    if actual_counts != expected_counts:
        errors.append(f"Unexpected frozen diagnostic counts: {actual_counts}")

    gates = report.get("quality_gates", {})
    if not gates or not all(value is True for value in gates.values()):
        errors.append("One or more report quality gates are not closed")
    confounding = report.get("collection_branch_confounding", {})
    if confounding.get("class_and_collection_branch_are_perfectly_confounded") is not True:
        errors.append("Expected collection-source/class confounding is not recorded")
    data_access = report.get("data_access", {})
    if (
        data_access.get("frozen_internal_test_rows_used") != 0
        or data_access.get("auxiliary_rows_used") != 0
        or data_access.get("quarantine_rows_used") != 0
    ):
        errors.append("Prohibited dataset rows were used")
    safety = report.get("safety_contract", {})
    required_safety = {
        "network_operations": 0,
        "model_fit_operations": 0,
        "threshold_changes": 0,
        "vectorizer_changes": 0,
        "labels_changed": 0,
        "pilot_used_for_model_selection": False,
        "training_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected in required_safety.items():
        if safety.get(key) != expected:
            errors.append(f"Report safety contract mismatch: {key}")

    registry_safety = registry.get("safety_contract", {})
    for key, expected in {
        "network_operations": 0,
        "labels_created": 0,
        "training_allowed": False,
        "domain_access_allowed": False,
        "deployment_allowed": False,
    }.items():
        if registry_safety.get(key) != expected:
            errors.append(f"Registry safety contract mismatch: {key}")
    decision = registry.get("decision", {})
    if (
        decision.get("model_configuration_remains_frozen") is not True
        or decision.get("tune_from_this_pilot") is not False
        or decision.get("promote_for_deployment") is not False
    ):
        errors.append("Registry decision gate is open")

    internal_artifacts = report.get("artifacts", {})
    for role, output_role in (("diagnostics", "diagnostics_jsonl"), ("error_queue", "error_queue_jsonl")):
        item = internal_artifacts.get(role, {})
        if item.get("sha256") != outputs.get(output_role, {}).get("sha256"):
            errors.append(f"Internal artifact hash mismatch: {role}")

    print(
        json.dumps(
            {
                "analysis_id": registry.get("analysis_id"),
                "valid": not errors,
                "counts": actual_counts,
                "checked": checked,
                "errors": errors,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
