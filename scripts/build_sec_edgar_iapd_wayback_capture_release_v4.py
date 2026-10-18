"""Build a V4 hash-bound capture release from an independently verified V7 plan."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from scripts.build_sec_edgar_iapd_wayback_capture_plan_v4 import (
    AVAILABILITY_REPORT_ID,
    PLAN_QA_ID,
    PLAN_QA_STATUS,
    PLAN_STATUS,
    REPORT_ID as PLAN_REPORT_ID,
)
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


# The identity remains V1 for the frozen capture report/executor schema.
RELEASE_ID = "ISI_SEC_EDGAR_IAPD_WAYBACK_CAPTURE_EXECUTION_RELEASE_V1"
RELEASE_QA_ID = "ISI_SEC_EDGAR_IAPD_WAYBACK_CAPTURE_RELEASE_INDEPENDENT_QA_V4"
RELEASE_QA_STATUS = "PASS_ARCHIVE_ONLY_CAPTURE_RELEASE"
MINIMUM_COOLDOWN_SECONDS = 86400


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed


def build_release(
    *, plan_path: Path, qa_path: Path, not_before: str,
    report_path: Path, created_at: str,
) -> dict[str, Any]:
    plan = load_object(plan_path)
    qa = load_object(qa_path)
    errors: list[str] = []
    if (
        plan.get("report_id") != PLAN_REPORT_ID
        or plan.get("status") != PLAN_STATUS
        or plan.get("tooling_version") != "v4"
        or plan.get("availability_generation") != "v7"
    ):
        errors.append("Capture plan is not an eligible V7-derived V4 plan")
    if int(plan.get("source_candidate_count", 0)) != 115:
        errors.append("Capture plan did not preserve the 115-row source population")
    if int(plan.get("planned_capture_count", 0)) < 1:
        errors.append("Capture plan is empty")
    plan_hash = sha256_file(plan_path)
    if qa.get("verification_id") != PLAN_QA_ID or qa.get("status") != PLAN_QA_STATUS:
        errors.append("Capture plan independent V4 QA did not pass")
    if qa.get("plan", {}).get("sha256") != plan_hash:
        errors.append("Capture plan independent QA hash mismatch")
    if qa.get("checks", {}).get("availability_generation") != "v7":
        errors.append("Capture plan QA generation binding mismatch")
    if qa.get("checks", {}).get("complete_115_row_population_recomputed") is not True:
        errors.append("Capture plan QA did not independently recompute all 115 rows")
    if qa.get("checks", {}).get("all_and_only_available_rows_planned_in_order") is not True:
        errors.append("Capture plan QA did not prove all-and-only-available order")
    if qa.get("decision", {}).get("capture_execution_release_may_be_prepared") is not True:
        errors.append("Capture plan QA did not release execution-release preparation")

    availability_item = plan.get("availability_result", {})
    final_created_at = availability_item.get("created_at")
    try:
        availability_time = parse_time(str(final_created_at))
        release_time = parse_time(created_at)
        gate_time = parse_time(not_before)
        required_not_before = availability_time + timedelta(seconds=MINIMUM_COOLDOWN_SECONDS)
        if gate_time < required_not_before:
            errors.append("not-before is less than 24 hours after final availability created_at")
        if gate_time < release_time:
            errors.append("not-before predates release creation")
    except (TypeError, ValueError) as error:
        required_not_before = None
        errors.append(str(error))

    availability_path = Path(str(availability_item.get("path", "")))
    try:
        if sha256_file(availability_path) != availability_item.get("sha256"):
            errors.append("Final V7 availability result hash mismatch")
        availability = load_object(availability_path)
        if availability.get("report_id") != AVAILABILITY_REPORT_ID:
            errors.append("Final V7 availability report identity changed")
        if availability.get("created_at") != final_created_at:
            errors.append("Final V7 availability created_at binding mismatch")
        if availability.get("status") != "COMPLETE" or availability.get("unresolved_error_count") != 0:
            errors.append("Final V7 availability result is not complete")
        if availability.get("capture_plan_construction_ready") is not True:
            errors.append("Final V7 availability kept capture-plan preparation closed")
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(f"Cannot read final V7 availability evidence: {error}")
    if report_path.exists() or report_path.with_suffix(report_path.suffix + ".partial").exists():
        errors.append("Capture report target already exists")
    if errors:
        raise ValueError(f"Capture release V4 validation failed: {errors}")

    return {
        "release_id": RELEASE_ID,
        "tooling_version": "v4",
        "created_at": created_at,
        "status": "FROZEN_HASH_BOUND_ARCHIVE_ONLY_CAPTURE_24H_NOT_BEFORE_GATE",
        "inputs": {
            "capture_plan": {
                "path": str(plan_path.resolve()), "sha256": plan_hash,
                "record_count": plan["planned_capture_count"],
            },
            "independent_capture_plan_qa": {
                "path": str(qa_path.resolve()), "sha256": sha256_file(qa_path),
                "verification_id": PLAN_QA_ID, "required_status": PLAN_QA_STATUS,
            },
            "final_availability_result": {
                "generation": "v7", "path": str(availability_path.resolve()),
                "sha256": availability_item["sha256"],
                "report_id": AVAILABILITY_REPORT_ID,
                "created_at": final_created_at,
            },
        },
        "cooldown_contract": {
            "availability_generation": "v7",
            "final_availability_created_at": str(final_created_at),
            "minimum_cooldown_seconds": MINIMUM_COOLDOWN_SECONDS,
            "required_not_before": required_not_before.isoformat(),
            "not_before": not_before,
        },
        "execution_contract": {
            "not_before": not_before,
            "allowed_network_hosts": ["web.archive.org"],
            "minimum_delay_seconds": 30.0,
            "maximum_attempts_per_snapshot": 1,
            "timeout_seconds": 30,
            "maximum_redirects": 3,
            "maximum_response_bytes": 26214400,
            "required_content_type_prefix": "text/html",
            "https_only": True,
            "raw_replay_modifier_required": True,
            "automatic_external_redirect_following": False,
            "stop_on_http_429": True,
            "errors_are_preserved": True,
            "failed_rows_are_not_replaced": True,
            "output_overwrite_allowed": False,
        },
        "planned_output": {
            "path": str(report_path.resolve()),
            "report_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_CAPTURE_REPORT_V1",
        },
        "decision": {
            "archive_only_capture_allowed_at_or_after_not_before": True,
            "candidate_live_domain_access_allowed": False,
            "text_extraction_allowed": False,
            "labeling_allowed": False,
            "validation_or_test_opening_allowed": False,
            "training_allowed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-qa", type=Path, required=True)
    parser.add_argument("--not-before", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    if args.output.exists() or partial.exists():
        raise FileExistsError("Refusing to overwrite capture execution release V4")
    release = build_release(
        plan_path=args.plan, qa_path=args.plan_qa, not_before=args.not_before,
        report_path=args.report, created_at=args.created_at,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps({
        "release_id": RELEASE_ID, "tooling_version": "v4",
        "output": str(args.output), "sha256": sha256_file(args.output),
        "not_before": release["execution_contract"]["not_before"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
