"""Verify the confirmed-branch pilot, provenance, review state, and closed gates."""

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
    root = args.registry.resolve().parents[2]
    errors: list[str] = []
    checked: list[dict[str, object]] = []

    if registry.get("pilot_id") != "EXTERNAL_TEXT_CONFIRMED_CAPTURE_PILOT_V1":
        errors.append("Unexpected pilot ID")
    if registry.get("status") != "TEN_DRAFTS_READY_FOR_HUMAN_RECONCILIATION_ZERO_ELIGIBLE":
        errors.append("Unexpected pilot status")

    for item in registry.get("inputs", {}).get("code_artifacts", []):
        path = root / str(item.get("path", ""))
        actual = sha256_file(path) if path.is_file() else None
        checked.append({"role": item.get("role"), "path": str(path), "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"Code artifact missing or changed: {item.get('role')}")

    outputs = {item.get("role"): item for item in registry.get("outputs", [])}
    expected_output_roles = {
        "intake_primary",
        "validation_primary",
        "first_pass_primary",
        "intake_reserve_v1",
        "validation_reserve_v1",
        "first_pass_reserve_v1",
        "intake_reserve_v2_001_030",
        "validation_reserve_v2_001_030",
        "first_pass_reserve_v2_001_030",
        "intake_reserve_v2_031_040",
        "validation_reserve_v2_031_040",
        "first_pass_reserve_v2_031_040",
        "confirmed_review_index_json",
        "confirmed_review_index_markdown",
    }
    if set(outputs) != expected_output_roles:
        errors.append("Output roles do not match the confirmed pilot contract")
    for role, item in outputs.items():
        path = Path(str(item.get("path", "")))
        actual = sha256_file(path) if path.is_file() else None
        checked.append({"role": role, "path": str(path), "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"Output missing or changed: {role}")

    intake_records = []
    for role in sorted(name for name in outputs if name.startswith("intake_")):
        batch = load_json(Path(outputs[role]["path"]))
        if batch.get("status") != "IN_REVIEW":
            errors.append(f"Intake is not IN_REVIEW: {role}")
        intake_records.extend(batch.get("records", []))
    if len(intake_records) != 10:
        errors.append("Combined intake must contain exactly ten records")
    for record in intake_records:
        if record.get("ground_truth_status") != "UNCERTAIN":
            errors.append(f"Record was labeled: {record.get('case_id')}")
        if record.get("label_confidence") != "LOW" or record.get("review_status") != "IN_REVIEW":
            errors.append(f"Record review state changed: {record.get('case_id')}")
        if any(item.get("reviewed") is not False for item in record.get("evidence", [])):
            errors.append(f"Evidence was reconciled: {record.get('case_id')}")
        artifact = record.get("artifact", {})
        raw_path = Path(str(registry["raw_root"])) / str(artifact.get("source_capture_path", ""))
        if not raw_path.is_file() or sha256_file(raw_path) != artifact.get("source_capture_sha256"):
            errors.append(f"Raw capture missing or changed: {record.get('case_id')}")

    validation_results = []
    for role in sorted(name for name in outputs if name.startswith("validation_")):
        report = load_json(Path(outputs[role]["path"]))
        validation_results.extend(report.get("record_results", []))
        if report.get("structural_error_count") != 0 or report.get("errors") != []:
            errors.append(f"Validation contains structural errors: {role}")
        if report.get("eligible_count") != 0 or report.get("reporting_allowed") is not False:
            errors.append(f"Validation gate is open: {role}")
    if len(validation_results) != 10 or not all(
        item.get("capture_valid") is True for item in validation_results
    ):
        errors.append("Not all ten intake capture hashes validate")

    first_pass_records = []
    for role in sorted(name for name in outputs if name.startswith("first_pass_")):
        report = load_json(Path(outputs[role]["path"]))
        first_pass_records.extend(report.get("records", []))
    if len(first_pass_records) != 10:
        errors.append("Combined first pass must contain exactly ten records")
    for item in first_pass_records:
        ai = item.get("ai_first_pass", {})
        if ai.get("recommended_outcome_for_human_review") != "CONFIRMED":
            errors.append(f"Unexpected first-pass outcome: {item.get('case_id')}")
        if ai.get("recommendation_is_ground_truth") is not False:
            errors.append(f"Recommendation was promoted to ground truth: {item.get('case_id')}")
        if item.get("record_state_changed") is not False or item.get("external_evaluation_eligible") is not False:
            errors.append(f"First pass opened a gate: {item.get('case_id')}")

    review_index = load_json(Path(outputs["confirmed_review_index_json"]["path"]))
    coverage = review_index.get("coverage", {})
    if coverage.get("record_count") != 10 or coverage.get("confirmed_recommendations_for_human_review") != 10:
        errors.append("Review index coverage mismatch")
    if coverage.get("human_reconciled_count") != 0 or coverage.get("external_evaluation_eligible_count") != 0:
        errors.append("Review index reports an open eligibility gate")

    wayback_manifests = sorted((root / "registry" / "manifests").glob("wayback_confirmed_capture__*.json"))
    warning_manifests = sorted((root / "registry" / "manifests").glob("official_warning_capture__*.json"))
    if len(wayback_manifests) != 10:
        errors.append("Expected exactly ten Wayback manifests")
    if len(warning_manifests) != 12:
        errors.append("Expected exactly twelve official-warning manifests")
    for manifest_path in [*wayback_manifests, *warning_manifests]:
        manifest = load_json(manifest_path)
        raw_path = Path(str(manifest.get("storage_path", "")))
        if not raw_path.is_file() or sha256_file(raw_path) != manifest.get("raw_file_sha256"):
            errors.append(f"Raw manifest mismatch: {manifest_path}")

    readiness = registry.get("readiness", {})
    if readiness.get("reviewable_confirmed_draft_count") != 10:
        errors.append("Readiness draft count mismatch")
    if readiness.get("human_reconciled_count") != 0 or readiness.get("eligible_confirmed_count") != 0:
        errors.append("Readiness gate is open")
    decision = registry.get("decision", {})
    if any(
        decision.get(field) is not False
        for field in ("promote_to_confirmed_label", "change_intake_record_state", "open_external_scoring")
    ):
        errors.append("Decision gate is open")
    safety = registry.get("safety_contract", {})
    if safety.get("live_candidate_domain_access_operations") != 0 or safety.get("labels_created") != 0:
        errors.append("Safety counts are invalid")
    if safety.get("training_allowed") is not False or safety.get("deployment_allowed") is not False:
        errors.append("Training/deployment gate is open")

    result = {
        "pilot_id": registry.get("pilot_id"),
        "status": "VALID" if not errors else "INVALID",
        "intake_record_count": len(intake_records),
        "capture_hash_valid_count": sum(item.get("capture_valid") is True for item in validation_results),
        "first_pass_recommendation_count": len(first_pass_records),
        "wayback_manifest_count": len(wayback_manifests),
        "official_warning_manifest_count": len(warning_manifests),
        "eligible_record_count": sum(item.get("eligible") is True for item in validation_results),
        "checked_artifacts": checked,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
