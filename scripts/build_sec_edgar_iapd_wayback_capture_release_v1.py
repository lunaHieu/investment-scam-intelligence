"""Build a hash-bound SEC/IAPD Wayback capture execution release."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.build_sec_edgar_iapd_wayback_capture_plan_v1 import REPORT_ID as PLAN_REPORT_ID
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


RELEASE_ID = "ISI_SEC_EDGAR_IAPD_WAYBACK_CAPTURE_EXECUTION_RELEASE_V1"
PLAN_QA_STATUS = "PASS_EXACT_AVAILABLE_SNAPSHOT_PLAN_REGISTER_BEFORE_EXECUTION"


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("not-before must include a timezone")
    return parsed


def build_release(
    *, plan_path: Path, qa_path: Path, not_before: str,
    report_path: Path, created_at: str,
) -> dict[str, Any]:
    plan = load_object(plan_path)
    qa = load_object(qa_path)
    errors: list[str] = []
    if plan.get("report_id") != PLAN_REPORT_ID:
        errors.append("Unexpected capture plan identity")
    if plan.get("status") != "FROZEN_ALL_AND_ONLY_AVAILABLE_V3_SNAPSHOTS_UNLABELED":
        errors.append("Capture plan is not frozen")
    if int(plan.get("planned_capture_count", 0)) < 1:
        errors.append("Capture plan is empty")
    if qa.get("status") != PLAN_QA_STATUS:
        errors.append("Capture plan independent QA did not pass")
    if qa.get("plan", {}).get("sha256") != sha256_file(plan_path):
        errors.append("Capture plan independent QA hash mismatch")
    if qa.get("decision", {}).get("capture_execution_release_may_be_prepared") is not True:
        errors.append("Capture plan QA did not release execution-release preparation")
    try:
        if parse_time(not_before) < parse_time(created_at):
            errors.append("not-before predates release creation")
    except (TypeError, ValueError) as error:
        errors.append(str(error))
    if report_path.exists() or report_path.with_suffix(report_path.suffix + ".partial").exists():
        errors.append("Capture report target already exists")
    if errors:
        raise ValueError(f"Capture release validation failed: {errors}")
    return {
        "release_id": RELEASE_ID,
        "created_at": created_at,
        "status": "FROZEN_HASH_BOUND_ARCHIVE_ONLY_CAPTURE_NOT_BEFORE_GATE",
        "inputs": {
            "capture_plan": {
                "path": str(plan_path.resolve()),
                "sha256": sha256_file(plan_path),
                "record_count": plan["planned_capture_count"],
            },
            "independent_capture_plan_qa": {
                "path": str(qa_path.resolve()),
                "sha256": sha256_file(qa_path),
                "required_status": PLAN_QA_STATUS,
            },
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
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite capture execution release")
    release = build_release(
        plan_path=args.plan,
        qa_path=args.plan_qa,
        not_before=args.not_before,
        report_path=args.report,
        created_at=args.created_at,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({"release_id": RELEASE_ID, "output": str(args.output), "sha256": sha256_file(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
