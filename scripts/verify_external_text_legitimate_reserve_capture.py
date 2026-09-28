"""Verify the SEC reserve capture pilot, provenance, first pass, and closed gates."""

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
    artifact_results: list[dict] = []

    if registry.get("pilot_id") != "EXTERNAL_TEXT_LEGITIMATE_RESERVE_CAPTURE_V1":
        errors.append("Unexpected pilot ID")
    if registry.get("status") != "NINE_RESERVE_CAPTURES_IN_REVIEW_ZERO_ELIGIBLE_RECORDS":
        errors.append("Unexpected pilot status")

    for key in ("normalizer", "capture_script", "preparation_script", "first_pass_script"):
        item = registry.get("inputs", {}).get(key, {})
        path = root / str(item.get("path", ""))
        actual = sha256_file(path) if path.is_file() else None
        artifact_results.append({"role": key, "path": str(path), "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"Code artifact missing or changed: {key}")

    raw_captures = registry.get("acquisition", {}).get("raw_captures", [])
    if len(raw_captures) != 9:
        errors.append("Pilot must contain exactly nine raw captures")
    for capture in raw_captures:
        path = Path(str(capture.get("path", "")))
        actual = sha256_file(path) if path.is_file() else None
        artifact_results.append({"role": "raw_capture", "path": str(path), "sha256": actual})
        if actual != capture.get("sha256"):
            errors.append(f"Raw capture missing or changed: {path}")
        elif path.stat().st_size != capture.get("bytes"):
            errors.append(f"Raw capture size changed: {path}")
        manifest_path = root / str(capture.get("manifest", ""))
        manifest = load_json(manifest_path) if manifest_path.is_file() else {}
        if manifest.get("raw_file_sha256") != capture.get("sha256"):
            errors.append(f"Capture manifest mismatch: {manifest_path}")

    outputs = {item.get("role"): item for item in registry.get("outputs", [])}
    expected_roles = {
        "initial_resolver_failure_report",
        "resolver_pinned_probe_report",
        "resolver_pinned_batch_report",
        "intake_draft_v1",
        "preparation_report_v1",
        "validation_report_v1",
        "ai_assisted_first_pass_v1",
    }
    if set(outputs) != expected_roles:
        errors.append("Output roles do not match the reserve capture contract")
    for role, item in outputs.items():
        path = Path(str(item.get("path", "")))
        actual = sha256_file(path) if path.is_file() else None
        artifact_results.append({"role": role, "path": str(path), "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"Output missing or changed: {role}")

    intake_path = Path(str(outputs.get("intake_draft_v1", {}).get("path", "")))
    intake = load_json(intake_path) if intake_path.is_file() else {}
    records = intake.get("records", [])
    if len(records) != 9:
        errors.append("Intake draft must contain exactly nine records")
    for record in records:
        if record.get("ground_truth_status") != "UNCERTAIN":
            errors.append(f"Record was labeled: {record.get('case_id')}")
        if record.get("label_confidence") != "LOW" or record.get("review_status") != "IN_REVIEW":
            errors.append(f"Record review state changed: {record.get('case_id')}")
        evidence = record.get("evidence", [])
        if len(evidence) != 1 or evidence[0].get("reviewed") is not False:
            errors.append(f"Record evidence was reconciled: {record.get('case_id')}")

    validation_path = Path(str(outputs.get("validation_report_v1", {}).get("path", "")))
    validation = load_json(validation_path) if validation_path.is_file() else {}
    if validation.get("structural_error_count") != 0 or validation.get("errors") != []:
        errors.append("Intake validation has structural errors")
    if validation.get("eligible_count") != 0 or validation.get("reporting_allowed") is not False:
        errors.append("Validation gate is open")
    if sum(item.get("capture_valid") is True for item in validation.get("record_results", [])) != 9:
        errors.append("Not all capture hashes validate")

    first_pass_path = Path(str(outputs.get("ai_assisted_first_pass_v1", {}).get("path", "")))
    first_pass = load_json(first_pass_path) if first_pass_path.is_file() else {}
    suggestions = first_pass.get("records", [])
    if len(suggestions) != 9:
        errors.append("First pass must contain exactly nine records")
    for suggestion in suggestions:
        current = suggestion.get("current_state", {})
        ai = suggestion.get("ai_first_pass", {})
        if current != {
            "ground_truth_status": "UNCERTAIN",
            "label_confidence": "LOW",
            "review_status": "IN_REVIEW",
        }:
            errors.append(f"First-pass current state changed: {suggestion.get('case_id')}")
        if ai.get("counts_as_label") is not False or ai.get("counts_as_human_review") is not False:
            errors.append(f"Suggestion was promoted: {suggestion.get('case_id')}")
    coverage = first_pass.get("coverage", {})
    if coverage.get("same_entity_likely_recommendations") != 9:
        errors.append("First-pass identity recommendation count mismatch")
    if coverage.get("human_confirmed_records") != 0 or coverage.get("labels_created") != 0:
        errors.append("First pass improperly reports human confirmation or labels")

    acquisition = registry.get("acquisition", {})
    if acquisition.get("successful_capture_count") != 9 or acquisition.get("http_status_rejection_count") != 1:
        errors.append("Acquisition counts mismatch")
    readiness = registry.get("readiness", {})
    if readiness.get("human_reconciled_count") != 0 or readiness.get("eligible_legitimate_count") != 0:
        errors.append("Readiness gate is open")
    decision = registry.get("decision", {})
    if any(
        decision.get(field) is not False
        for field in ("promote_to_legitimate_label", "change_intake_record_state", "open_external_scoring")
    ):
        errors.append("Decision gate is open")
    safety = registry.get("safety_contract", {})
    if safety.get("live_suspicious_domain_access_operations") != 0 or safety.get("labels_created") != 0:
        errors.append("Safety counts are invalid")
    if safety.get("training_allowed") is not False or safety.get("deployment_allowed") is not False:
        errors.append("Training/deployment gate is open")

    result = {
        "pilot_id": registry.get("pilot_id"),
        "status": "VALID" if not errors else "INVALID",
        "raw_capture_count": len(raw_captures),
        "intake_record_count": len(records),
        "same_entity_likely_recommendation_count": coverage.get("same_entity_likely_recommendations"),
        "eligible_record_count": validation.get("eligible_count"),
        "artifact_results": artifact_results,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
