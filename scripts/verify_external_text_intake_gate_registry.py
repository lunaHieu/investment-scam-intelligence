"""Verify the frozen external-text intake gate registry and template report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from validate_external_text_intake import sha256_file


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    args = parser.parse_args()
    registry = load_json(args.registry)
    errors: list[str] = []
    if registry.get("analysis_id") != "ISI_EXTERNAL_TEXT_INTAKE_GATE_V1":
        errors.append("Unexpected analysis ID")
    if registry.get("status") != "TWENTY_ONE_DRAFTS_IN_REVIEW_BLOCKED_ZERO_ELIGIBLE_RECORDS":
        errors.append("Unexpected intake-gate status")

    repository_root = args.registry.resolve().parents[2]
    input_results = []
    roles = set()
    for item in registry.get("inputs", []):
        role = str(item.get("role") or "")
        roles.add(role)
        path = Path(item.get("path", ""))
        if not path.is_absolute():
            path = repository_root / path
        actual_hash = sha256_file(path) if path.is_file() else None
        if actual_hash != item.get("sha256"):
            errors.append(f"Input SHA-256 mismatch: {role}")
        input_results.append({"role": role, "path": str(path), "sha256": actual_hash})
    expected_roles = {
        "intake_template",
        "validator",
        "workflow_documentation",
        "legitimate_primary_capture_registry",
        "legitimate_reserve_queue_registry",
        "legitimate_reserve_capture_registry",
        "confirmed_capture_registry",
    }
    if roles != expected_roles or len(registry.get("inputs", [])) != len(expected_roles):
        errors.append("Input roles are incomplete or duplicated")

    validation = registry.get("template_validation", {})
    report_path = Path(validation.get("report_path", ""))
    report_hash = sha256_file(report_path) if report_path.is_file() else None
    if report_hash != validation.get("report_sha256"):
        errors.append("Template validation report SHA-256 mismatch")
    report = load_json(report_path) if report_path.is_file() else {}
    if report.get("structural_error_count") != 0 or report.get("errors") != []:
        errors.append("Template must have zero structural errors")
    if report.get("eligible_count") != 0:
        errors.append("Empty template cannot contain eligible records")
    if report.get("reporting_allowed") is not False:
        errors.append("Empty template cannot open the reporting gate")
    safety = report.get("safety_contract", {})
    if safety.get("network_operations") != 0:
        errors.append("Template validation must be offline")
    if safety.get("model_scoring_operations") != 0 or safety.get("labels_created") != 0:
        errors.append("Template validation cannot score or label")

    decision = registry.get("decision", {})
    if decision.get("external_text_scoring_performed") is not False:
        errors.append("Registry cannot report external scoring")
    if decision.get("reporting_gate_open") is not False:
        errors.append("Registry reporting gate must remain closed")
    registry_safety = registry.get("safety_contract", {})
    if registry_safety.get("training_allowed") is not False:
        errors.append("Registry training gate must remain closed")
    if registry_safety.get("domain_access_allowed") is not False:
        errors.append("Registry domain-access gate must remain closed")
    inventory = registry.get("raw_inventory", {})
    if inventory.get("external_text_capture_files") != 33:
        errors.append("Expected thirty-three external HTML captures")
    if inventory.get("external_warning_evidence_files") != 12:
        errors.append("Expected twelve official warning evidence captures")
    if inventory.get("external_text_draft_records") != 21:
        errors.append("Expected twenty-one external draft records")
    if inventory.get("external_text_confirmed_draft_records") != 10:
        errors.append("Expected ten confirmed-branch draft records")
    if inventory.get("external_text_legitimate_draft_records") != 11:
        errors.append("Expected eleven legitimate-branch draft records")
    if inventory.get("external_text_eligible_records") != 0:
        errors.append("External eligible count must remain zero")

    result = {
        "analysis_id": registry.get("analysis_id"),
        "status": "VALID" if not errors else "INVALID",
        "eligible_records": report.get("eligible_count"),
        "reporting_allowed": report.get("reporting_allowed"),
        "template_report_sha256": report_hash,
        "input_results": input_results,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
