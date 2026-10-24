"""Freeze a separate archive-only capture release for the two V11 rows."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from scripts.build_sec_edgar_iapd_v11_supplemental_capture_plan import (
    AVAILABILITY_REPORT_ID,
    EXPECTED_IDS,
    PLAN_STATUS,
    QA_ID,
    QA_STATUS,
    REPORT_ID as PLAN_REPORT_ID,
)
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import (
    load_object,
    sha256_file,
)


RELEASE_ID = "ISI_SEC_EDGAR_IAPD_V11_SUPPLEMENTAL_CAPTURE_RELEASE_V1"
RELEASE_QA_ID = "ISI_SEC_EDGAR_IAPD_V11_SUPPLEMENTAL_CAPTURE_RELEASE_INDEPENDENT_QA_V1"
RELEASE_QA_STATUS = "PASS_ARCHIVE_ONLY_V11_SUPPLEMENTAL_CAPTURE_RELEASE"
MINIMUM_COOLDOWN_SECONDS = 86400


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed


def build_release(
    *, plan_path: Path, plan_qa_path: Path, availability_path: Path,
    availability_qa_path: Path, not_before: str, report_path: Path, created_at: str,
) -> dict[str, Any]:
    plan = load_object(plan_path)
    plan_qa = load_object(plan_qa_path)
    availability = load_object(availability_path)
    availability_qa = load_object(availability_qa_path)
    errors: list[str] = []
    plan_hash = sha256_file(plan_path)
    plan_qa_hash = sha256_file(plan_qa_path)
    availability_hash = sha256_file(availability_path)
    availability_qa_hash = sha256_file(availability_qa_path)
    if (
        plan.get("report_id") != PLAN_REPORT_ID
        or plan.get("status") != PLAN_STATUS
        or plan.get("tooling_version") != "v11-supplemental-v1"
        or plan.get("availability_generation") != "v11"
    ):
        errors.append("Plan is not an eligible V11 supplemental plan")
    if plan.get("planned_capture_count") != 2 or plan.get("ordered_supplemental_ids") != list(EXPECTED_IDS):
        errors.append("Plan does not contain the exact two V11 supplemental rows")
    if plan_qa.get("verification_id") != QA_ID or plan_qa.get("status") != QA_STATUS:
        errors.append("Independent supplemental plan QA did not pass")
    if plan_qa.get("plan", {}).get("sha256") != plan_hash:
        errors.append("Supplemental plan/QA hash binding mismatch")
    if availability.get("report_id") != AVAILABILITY_REPORT_ID or availability.get("status") != "COMPLETE":
        errors.append("V11 availability evidence is not complete")
    if availability_qa.get("inputs", {}).get("report_sha256") != availability_hash:
        errors.append("V11 availability QA/result hash binding mismatch")

    try:
        availability_time = parse_time(str(availability.get("created_at")))
        release_time = parse_time(created_at)
        gate_time = parse_time(not_before)
        required_not_before = availability_time + timedelta(seconds=MINIMUM_COOLDOWN_SECONDS)
        if gate_time < required_not_before:
            errors.append("not-before is less than 24 hours after V11 availability report")
        if gate_time < release_time:
            errors.append("not-before predates release creation")
    except (TypeError, ValueError) as error:
        required_not_before = None
        errors.append(str(error))

    report_partial = report_path.with_suffix(report_path.suffix + ".partial")
    if report_path.exists() or report_partial.exists():
        errors.append("Supplemental capture report target already exists")
    if errors:
        raise ValueError(f"V11 supplemental capture-release validation failed: {errors}")

    return {
        "release_id": RELEASE_ID,
        "tooling_version": "v11-supplemental-v1",
        "created_at": created_at,
        "status": "FROZEN_HASH_BOUND_ARCHIVE_ONLY_SUPPLEMENTAL_CAPTURE_24H_GATE",
        "inputs": {
            "capture_plan": {"path": str(plan_path.resolve()), "sha256": plan_hash, "record_count": 2},
            "independent_capture_plan_qa": {
                "path": str(plan_qa_path.resolve()), "sha256": plan_qa_hash,
                "verification_id": QA_ID, "required_status": QA_STATUS,
            },
            "final_v11_availability_result": {
                "path": str(availability_path.resolve()), "sha256": availability_hash,
                "report_id": AVAILABILITY_REPORT_ID, "created_at": availability.get("created_at"),
            },
            "independent_v11_availability_qa": {
                "path": str(availability_qa_path.resolve()), "sha256": availability_qa_hash,
            },
        },
        "supplemental_identity_contract": {
            "ordered_availability_plan_ids": list(EXPECTED_IDS),
            "cohort": "EXTERNAL_HOLDOUT",
            "original_58_row_capture_plan_mutation_allowed": False,
            "original_56_row_review_population_mutation_allowed": False,
        },
        "cooldown_contract": {
            "availability_generation": "v11",
            "final_availability_created_at": availability.get("created_at"),
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
            "partial_journal_reserved_before_network": True,
            "automatic_resume_allowed": False,
        },
        "planned_output": {
            "path": str(report_path.resolve()),
            "report_id": "ISI_SEC_EDGAR_IAPD_V11_SUPPLEMENTAL_CAPTURE_REPORT_V1",
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
    parser.add_argument("--availability", type=Path, required=True)
    parser.add_argument("--availability-qa", type=Path, required=True)
    parser.add_argument("--not-before", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite V11 supplemental capture release")
    release = build_release(
        plan_path=args.plan, plan_qa_path=args.plan_qa,
        availability_path=args.availability, availability_qa_path=args.availability_qa,
        not_before=args.not_before, report_path=args.report, created_at=args.created_at,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps({
        "release_id": RELEASE_ID,
        "output": str(args.output),
        "sha256": sha256_file(args.output),
        "not_before": release["execution_contract"]["not_before"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
