"""Independently verify the V11 metadata-recovery release offline."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

from scripts.build_sec_edgar_iapd_v11_metadata_recovery_release import (
    EXPECTED_IDS,
    MINIMUM_COOLDOWN_SECONDS,
    PLAN_ID,
    PLAN_QA_STATUS,
    RELEASE_ID,
    RELEASE_QA_ID,
    RELEASE_QA_STATUS,
    parse_time,
)
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def verify(release_path: Path) -> dict:
    release = load_object(release_path)
    errors: list[str] = []
    if release.get("release_id") != RELEASE_ID:
        errors.append("unexpected recovery release identity")
    inputs = release.get("inputs", {})
    plan_path = Path(str(inputs.get("recovery_plan", {}).get("path", "")))
    plan_qa_path = Path(str(inputs.get("recovery_plan_qa", {}).get("path", "")))
    try:
        plan = load_object(plan_path)
        plan_qa = load_object(plan_qa_path)
        if sha256_file(plan_path) != inputs["recovery_plan"]["sha256"]:
            errors.append("recovery plan hash mismatch")
        if plan.get("report_id") != PLAN_ID or plan.get("ordered_ids") != list(EXPECTED_IDS) or plan.get("planned_capture_count") != 2:
            errors.append("recovery plan identity/order/count mismatch")
        if plan_qa.get("status") != PLAN_QA_STATUS or plan_qa.get("plan_sha256") != sha256_file(plan_path):
            errors.append("recovery plan QA mismatch")
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        errors.append(f"recovery plan evidence unreadable: {error}")
    try:
        availability = load_object(Path(str(inputs["availability_result"]["path"])))
        availability_path = Path(str(inputs["availability_result"]["path"]))
        if availability.get("status") != "COMPLETE" or sha256_file(availability_path) != inputs["availability_result"]["sha256"]:
            errors.append("availability evidence mismatch")
        if parse_time(str(release["cooldown_contract"]["not_before"])) < parse_time(str(availability["created_at"])) + timedelta(seconds=MINIMUM_COOLDOWN_SECONDS):
            errors.append("recovery cooldown is shorter than 24 hours")
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        errors.append(f"availability evidence unreadable: {error}")
    report_path = Path(str(release.get("planned_output", {}).get("path", "")))
    if report_path.exists() or report_path.with_suffix(report_path.suffix + ".partial").exists():
        errors.append("recovery report target already exists")
    contract = release.get("execution_contract", {})
    if contract.get("allowed_network_hosts") != ["web.archive.org"] or contract.get("minimum_delay_seconds") != 30.0 or contract.get("maximum_attempts_per_snapshot") != 1 or contract.get("stop_on_http_429") is not True or contract.get("output_overwrite_allowed") is not False:
        errors.append("recovery execution safety contract changed")
    decision = release.get("decision", {})
    for gate in ("candidate_live_domain_access_allowed", "text_extraction_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "training_allowed"):
        if decision.get(gate) is not False:
            errors.append(f"forbidden gate opened: {gate}")
    return {"verification_id": RELEASE_QA_ID, "status": RELEASE_QA_STATUS if not errors else "FAIL", "release": {"path": str(release_path.resolve()), "sha256": sha256_file(release_path)}, "checks": {"exact_two_row_order": not any("identity/order/count" in error for error in errors), "plan_hash_verified": not any("plan hash" in error for error in errors), "cooldown_seconds": MINIMUM_COOLDOWN_SECONDS, "planned_output_absent": not report_path.exists() and not report_path.with_suffix(report_path.suffix + ".partial").exists(), "network_operations": 0}, "decision": {"release_qa_passed": not errors, "execution_allowed_at_or_after_not_before": not errors, "text_extraction_allowed": False, "training_allowed": False}, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite recovery release QA")
    result = verify(args.release)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
