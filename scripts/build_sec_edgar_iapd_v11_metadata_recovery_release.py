"""Build a separately frozen V11 metadata-recovery plan and release offline."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from scripts.build_sec_edgar_iapd_v11_supplemental_capture_plan import EXPECTED_IDS
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


PLAN_ID = "ISI_SEC_EDGAR_IAPD_V11_METADATA_RECOVERY_PLAN_V1"
RELEASE_ID = "ISI_SEC_EDGAR_IAPD_V11_METADATA_RECOVERY_RELEASE_V1"
PLAN_QA_ID = "ISI_SEC_EDGAR_IAPD_V11_METADATA_RECOVERY_PLAN_INDEPENDENT_QA_V1"
RELEASE_QA_ID = "ISI_SEC_EDGAR_IAPD_V11_METADATA_RECOVERY_RELEASE_INDEPENDENT_QA_V1"
PLAN_QA_STATUS = "PASS_EXACT_TWO_ROW_V11_METADATA_RECOVERY_PLAN"
RELEASE_QA_STATUS = "PASS_ARCHIVE_ONLY_V11_METADATA_RECOVERY_RELEASE"
MINIMUM_COOLDOWN_SECONDS = 86400


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed


def build_plan(source_plan_path: Path, source_plan_sha256: str, raw_root: Path) -> dict[str, Any]:
    if sha256_file(source_plan_path) != source_plan_sha256:
        raise ValueError("source supplemental plan hash mismatch")
    source = load_object(source_plan_path)
    rows = list(source.get("results", []))
    if [row.get("availability_plan_id") for row in rows] != list(EXPECTED_IDS):
        raise ValueError("source plan identity/order changed")
    results: list[dict[str, Any]] = []
    for row in rows:
        target = raw_root / str(row["cohort"]) / f"{row['availability_plan_id']}__{row['candidate_host']}.html"
        if target.exists():
            raise FileExistsError(f"metadata-recovery raw target already exists: {target}")
        results.append({
            **row,
            "source_capture_path": row["capture_path"],
            "capture_path": str(target),
            "plan_status": "PLANNED_NOT_EXECUTED_METADATA_RECOVERY",
            "artifact_captured": False,
            "archived_page_downloaded": False,
            "wayback_queried": False,
        })
    return {
        "report_id": PLAN_ID,
        "created_at": datetime.now().astimezone().isoformat(),
        "status": "FROZEN_EXACT_TWO_ROW_V11_METADATA_RECOVERY_PLAN",
        "tooling_version": "v11-metadata-recovery-v1",
        "source_plan": {"path": str(source_plan_path.resolve()), "sha256": source_plan_sha256, "record_count": len(rows)},
        "ordered_ids": list(EXPECTED_IDS),
        "planned_capture_count": len(results),
        "planned_by_cohort": {"EXTERNAL_HOLDOUT": len(results)},
        "raw_root": str(raw_root.resolve()),
        "results": results,
        "historical_mutation_allowed": False,
        "decision": {"network_allowed": False, "capture_allowed_after_release_gate": True, "text_extraction_allowed": False, "labeling_allowed": False, "training_allowed": False},
    }


def build_release(plan_path: Path, plan_qa_path: Path, availability_path: Path, availability_qa_path: Path, failed_reservation_path: Path, created_at: str, not_before: str, report_path: Path) -> dict[str, Any]:
    plan = load_object(plan_path)
    plan_qa = load_object(plan_qa_path)
    availability = load_object(availability_path)
    availability_qa = load_object(availability_qa_path)
    reservation = load_object(failed_reservation_path)
    errors: list[str] = []
    if plan.get("report_id") != PLAN_ID or plan.get("ordered_ids") != list(EXPECTED_IDS) or plan.get("planned_capture_count") != 2:
        errors.append("metadata-recovery plan identity/count invalid")
    if plan_qa.get("status") != PLAN_QA_STATUS or plan_qa.get("plan_sha256") != sha256_file(plan_path):
        errors.append("metadata-recovery plan QA invalid")
    if availability.get("status") != "COMPLETE" or availability_qa.get("inputs", {}).get("report_sha256") != sha256_file(availability_path):
        errors.append("V11 availability evidence invalid")
    try:
        required = parse_time(str(availability["created_at"])) + timedelta(seconds=MINIMUM_COOLDOWN_SECONDS)
        gate = parse_time(not_before)
        release_time = parse_time(created_at)
        if gate < required or gate < release_time:
            errors.append("metadata-recovery not-before cooldown invalid")
    except (KeyError, ValueError, TypeError) as error:
        errors.append(f"invalid timestamps: {error}")
    if reservation.get("status") != "RESERVED_BEFORE_NETWORK_NON_RESUMABLE":
        errors.append("failed reservation evidence changed")
    if report_path.exists() or report_path.with_suffix(report_path.suffix + ".partial").exists():
        errors.append("metadata-recovery report target already exists")
    if errors:
        raise ValueError(f"metadata-recovery release validation failed: {errors}")
    return {
        "release_id": RELEASE_ID,
        "tooling_version": "v11-metadata-recovery-v1",
        "created_at": created_at,
        "status": "FROZEN_HASH_BOUND_ARCHIVE_ONLY_V11_METADATA_RECOVERY_24H_GATE",
        "inputs": {
            "recovery_plan": {"path": str(plan_path.resolve()), "sha256": sha256_file(plan_path), "record_count": 2},
            "recovery_plan_qa": {"path": str(plan_qa_path.resolve()), "sha256": sha256_file(plan_qa_path), "required_status": PLAN_QA_STATUS},
            "availability_result": {"path": str(availability_path.resolve()), "sha256": sha256_file(availability_path), "created_at": availability["created_at"]},
            "availability_qa": {"path": str(availability_qa_path.resolve()), "sha256": sha256_file(availability_qa_path)},
            "failed_reservation": {"path": str(failed_reservation_path.resolve()), "sha256": sha256_file(failed_reservation_path)},
        },
        "identity_contract": {"ordered_ids": list(EXPECTED_IDS), "cohort": "EXTERNAL_HOLDOUT", "original_snapshot_mutation_allowed": False},
        "cooldown_contract": {"minimum_cooldown_seconds": MINIMUM_COOLDOWN_SECONDS, "not_before": not_before},
        "execution_contract": {"not_before": not_before, "allowed_network_hosts": ["web.archive.org"], "minimum_delay_seconds": 30.0, "maximum_attempts_per_snapshot": 1, "timeout_seconds": 30, "maximum_redirects": 3, "maximum_response_bytes": 26214400, "required_content_type_prefix": "text/html", "raw_replay_modifier_required": True, "automatic_external_redirect_following": False, "stop_on_http_429": True, "partial_journal_reserved_before_network": True, "automatic_resume_allowed": False, "output_overwrite_allowed": False},
        "planned_output": {"path": str(report_path.resolve()), "report_id": "ISI_SEC_EDGAR_IAPD_V11_METADATA_RECOVERY_REPORT_V1"},
        "user_agent": "ISI-V11-Metadata-Recovery-Capture/1.0 (gpt-5; https://github.com/lunaHieu/investment-scam-intelligence)",
        "decision": {"archive_only_capture_allowed_at_or_after_not_before": True, "candidate_live_domain_access_allowed": False, "text_extraction_allowed": False, "labeling_allowed": False, "validation_or_test_opening_allowed": False, "training_allowed": False},
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists() or path.with_suffix(path.suffix + ".partial").exists():
        raise FileExistsError(f"Refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-plan", type=Path, required=True)
    parser.add_argument("--source-plan-sha256", required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-qa", type=Path, required=True)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-qa", type=Path, required=True)
    parser.add_argument("--availability", type=Path, required=True)
    parser.add_argument("--availability-qa", type=Path, required=True)
    parser.add_argument("--failed-reservation", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--not-before", required=True)
    args = parser.parse_args()
    if args.plan.exists() and args.plan_qa.exists():
        # A crash after plan materialization must be recoverable without
        # overwriting either frozen preparation artifact.
        plan = load_object(args.plan)
        plan_qa = load_object(args.plan_qa)
        if plan.get("report_id") != PLAN_ID or plan_qa.get("status") != PLAN_QA_STATUS or plan_qa.get("plan_sha256") != sha256_file(args.plan):
            raise ValueError("existing metadata-recovery plan/QA pair is not reusable")
    elif args.plan.exists() or args.plan_qa.exists():
        raise FileExistsError("metadata-recovery plan/QA pair is incomplete; refusing overwrite")
    else:
        plan = build_plan(args.source_plan, args.source_plan_sha256, args.raw_root)
        write_json(args.plan, plan)
        plan_qa = {"verification_id": PLAN_QA_ID, "status": PLAN_QA_STATUS, "plan_sha256": sha256_file(args.plan), "ordered_ids": list(EXPECTED_IDS), "checks": {"network_operations": 0, "labels_created": 0, "training_allowed": False}, "errors": []}
        write_json(args.plan_qa, plan_qa)
    release = build_release(args.plan, args.plan_qa, args.availability, args.availability_qa, args.failed_reservation, args.created_at, args.not_before, args.report)
    write_json(args.release, release)
    release_qa = {"verification_id": RELEASE_QA_ID, "status": RELEASE_QA_STATUS, "release_sha256": sha256_file(args.release), "plan_sha256": sha256_file(args.plan), "not_before": args.not_before, "errors": []}
    write_json(args.release_qa, release_qa)
    print(json.dumps({"plan_sha256": sha256_file(args.plan), "release_sha256": sha256_file(args.release), "not_before": args.not_before}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
