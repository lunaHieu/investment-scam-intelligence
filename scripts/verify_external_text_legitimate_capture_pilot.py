"""Verify the SEC-linked external-text capture pilot and its closed gate."""

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
    parser.add_argument("--registry", required=True, type=Path)
    args = parser.parse_args()
    registry = load_json(args.registry)
    root = args.registry.resolve().parents[2]
    errors: list[str] = []
    artifact_results = []

    if registry.get("pilot_id") != "EXTERNAL_TEXT_LEGIT_CAPTURE_PILOT_V1":
        errors.append("Unexpected pilot ID")
    if registry.get("status") != "TWO_CAPTURES_IN_REVIEW_ZERO_ELIGIBLE_RECORDS":
        errors.append("Unexpected pilot status")

    for capture in registry.get("acquisition", {}).get("raw_captures", []):
        path = Path(str(capture.get("path", "")))
        actual = sha256_file(path) if path.is_file() else None
        artifact_results.append({"role": "raw_capture", "path": str(path), "sha256": actual})
        if actual != capture.get("sha256") or path.stat().st_size != capture.get("bytes"):
            errors.append(f"Raw capture missing or changed: {path}")
        manifest_path = root / str(capture.get("manifest", ""))
        manifest = load_json(manifest_path) if manifest_path.is_file() else {}
        if manifest.get("raw_file_sha256") != capture.get("sha256"):
            errors.append(f"Capture manifest mismatch: {manifest_path}")

    outputs = {item.get("role"): item for item in registry.get("outputs", [])}
    if set(outputs) != {
        "intake_draft_v2",
        "preparation_report_v2",
        "validation_report_v2",
        "capture_run_006_015_v1",
    }:
        errors.append("Output roles do not match the pilot contract")
    for role, item in outputs.items():
        path = Path(str(item.get("path", "")))
        actual = sha256_file(path) if path.is_file() else None
        artifact_results.append({"role": role, "path": str(path), "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"Output missing or changed: {role}")

    draft_path = Path(str(outputs.get("intake_draft_v2", {}).get("path", "")))
    draft = load_json(draft_path) if draft_path.is_file() else {}
    records = draft.get("records", [])
    if len(records) != 2:
        errors.append("Intake draft must contain exactly two records")
    for record in records:
        if record.get("ground_truth_status") != "UNCERTAIN":
            errors.append(f"Draft record was labeled: {record.get('case_id')}")
        if record.get("label_confidence") != "LOW" or record.get("review_status") != "IN_REVIEW":
            errors.append(f"Draft review state is invalid: {record.get('case_id')}")
        evidence = record.get("evidence", [])
        if len(evidence) != 1 or evidence[0].get("reviewed") is not False:
            errors.append(f"Draft evidence was improperly reconciled: {record.get('case_id')}")

    validation_path = Path(str(outputs.get("validation_report_v2", {}).get("path", "")))
    validation = load_json(validation_path) if validation_path.is_file() else {}
    if validation.get("structural_error_count") != 0 or validation.get("errors") != []:
        errors.append("Intake draft has structural validation errors")
    if validation.get("eligible_count") != 0 or validation.get("reporting_allowed") is not False:
        errors.append("Pilot must remain ineligible and blocked")
    if sum(item.get("capture_valid") is True for item in validation.get("record_results", [])) != 2:
        errors.append("Both capture hashes must validate")

    readiness = registry.get("readiness", {})
    if readiness.get("eligible_legitimate_count") != 0 or readiness.get("reporting_allowed") is not False:
        errors.append("Registry readiness gate is open")
    safety = registry.get("safety_contract", {})
    if safety.get("live_suspicious_domain_access_operations") != 0:
        errors.append("Pilot cannot access live suspicious domains")
    if safety.get("labels_created") != 0 or safety.get("model_scoring_operations") != 0:
        errors.append("Pilot cannot label or score")
    if safety.get("training_allowed") is not False or safety.get("deployment_allowed") is not False:
        errors.append("Training/deployment gate is open")
    acquisition = registry.get("acquisition", {})
    if acquisition.get("attempted_candidate_count") != 15:
        errors.append("Acquisition attempt count mismatch")
    if acquisition.get("successful_capture_count") != 2:
        errors.append("Acquisition success count mismatch")
    if acquisition.get("retryable_environment_failure_count") != 10:
        errors.append("Retryable environment failure count mismatch")

    result = {
        "pilot_id": registry.get("pilot_id"),
        "status": "VALID" if not errors else "INVALID",
        "raw_capture_count": len(registry.get("acquisition", {}).get("raw_captures", [])),
        "intake_record_count": len(records),
        "eligible_record_count": validation.get("eligible_count"),
        "artifact_results": artifact_results,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
