"""Build an offline, hash-bound retry release for partial SEC/IAPD captures."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from scripts.capture_balanced_wayback_plan_v2 import assert_archive_url
from scripts.verify_sec_edgar_iapd_wayback_capture_result_v1 import (
    verify as verify_source_capture_result,
)
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import (
    load_object,
    sha256_file,
)


RELEASE_ID = "ISI_SEC_EDGAR_IAPD_WAYBACK_CAPTURE_MISSING_ROW_RETRY_RELEASE_V1"
PARTIAL_QA_ID = "ISI_SEC_EDGAR_IAPD_WAYBACK_CAPTURE_RESULT_INDEPENDENT_QA_V1"
PARTIAL_QA_STATUS = "PASS_PARTIAL_CAPTURE_RETRY_REQUIRED_TEXT_EXTRACTION_BLOCKED"
SOURCE_RELEASE_ID = "ISI_SEC_EDGAR_IAPD_WAYBACK_CAPTURE_EXECUTION_RELEASE_V1"
SOURCE_RELEASE_QA_STATUS = "PASS_ARCHIVE_ONLY_CAPTURE_RELEASE"
EXPECTED_PARTIAL_QA_DECISION = {
    "capture_result_qa_passed": True,
    "text_extraction_release_may_be_prepared": False,
    "capture_retry_required": True,
    "candidate_live_domain_access_allowed": False,
    "labeling_allowed": False,
    "validation_or_test_opening_allowed": False,
    "training_allowed": False,
}
EXPECTED_PARTIAL_QA_SAFETY = {
    "network_operations": 0,
    "raw_files_modified": 0,
    "labels": 0,
    "model": 0,
}
RETRY_OUTCOMES = {"FAILED", "NOT_ATTEMPTED_AFTER_HTTP_429_STOP"}
IDENTITY_KEYS = (
    "availability_plan_id",
    "shortlist_id",
    "cohort",
    "candidate_host",
    "candidate_url",
    "snapshot_timestamp",
    "snapshot_url",
    "requested_archive_url",
    "capture_path",
)
def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must include a timezone")
    return parsed


def _identity(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row.get(key) for key in IDENTITY_KEYS}


def build_retry_release(
    *,
    partial_qa_path: Path,
    source_release_path: Path,
    source_release_qa_path: Path,
    capture_report_path: Path,
    not_before: str,
    report_path: Path,
    created_at: str,
) -> dict[str, Any]:
    qa = load_object(partial_qa_path)
    errors: list[str] = []
    if qa.get("verification_id") != PARTIAL_QA_ID:
        errors.append("Unexpected independent capture QA identity")
    if qa.get("status") != PARTIAL_QA_STATUS:
        errors.append("Independent capture QA is not a passing partial result")
    if qa.get("errors") != []:
        errors.append("Independent capture QA contains errors")
    if qa.get("decision") != EXPECTED_PARTIAL_QA_DECISION:
        errors.append("Independent capture QA decisions do not match a passing partial result")
    if qa.get("safety_contract") != EXPECTED_PARTIAL_QA_SAFETY:
        errors.append("Independent capture QA safety contract changed")

    source_release_path = source_release_path.resolve()
    source_release_qa_path = source_release_qa_path.resolve()
    capture_report_path = capture_report_path.resolve()
    for role, path in (
        ("source capture release", source_release_path),
        ("source capture release QA", source_release_qa_path),
        ("capture report", capture_report_path),
    ):
        if not path.is_file():
            errors.append(f"Missing {role}: {path}")
    if errors:
        raise ValueError(f"Capture retry release validation failed: {errors}")

    source_release = load_object(source_release_path)
    source_release_qa = load_object(source_release_qa_path)
    report = load_object(capture_report_path)
    source_release_hash = sha256_file(source_release_path)
    source_release_qa_hash = sha256_file(source_release_qa_path)
    capture_report_hash = sha256_file(capture_report_path)
    recomputed_qa = verify_source_capture_result(
        source_release_path, source_release_qa_path, capture_report_path
    )
    if qa != recomputed_qa:
        errors.append("Independent capture QA does not equal a full recomputation")
    if source_release.get("release_id") != SOURCE_RELEASE_ID:
        errors.append("Unexpected source capture release identity")
    if source_release_qa.get("status") != SOURCE_RELEASE_QA_STATUS:
        errors.append("Source capture release QA did not pass")
    if source_release_qa.get("release", {}).get("sha256") != source_release_hash:
        errors.append("Source capture release QA hash mismatch")
    plan_item = source_release.get("inputs", {}).get("capture_plan", {})
    plan_path = Path(str(plan_item.get("path", "")))
    if not plan_path.is_absolute() or not plan_path.is_file():
        errors.append("Source capture plan path is missing or not absolute")
        plan = {}
        plan_hash = ""
    else:
        plan_hash = sha256_file(plan_path)
        if plan_item.get("sha256") != plan_hash:
            errors.append("Source capture plan hash mismatch")
        plan = load_object(plan_path)
    qa_inputs = qa.get("inputs", {})
    expected_qa_inputs = {
        "release_sha256": source_release_hash,
        "release_qa_sha256": source_release_qa_hash,
        "report_sha256": capture_report_hash,
        "plan_sha256": plan_hash,
    }
    if qa_inputs != expected_qa_inputs:
        errors.append("Independent capture QA input hashes do not match explicit sources")
    if report.get("report_id") != source_release.get("planned_output", {}).get("report_id"):
        errors.append("Capture report identity does not match source release")
    if report.get("release", {}).get("sha256") != source_release_hash:
        errors.append("Capture report source-release hash mismatch")
    if report.get("release_qa", {}).get("sha256") != source_release_qa_hash:
        errors.append("Capture report source-release-QA hash mismatch")
    if report.get("plan") != plan_item:
        errors.append("Capture report plan binding mismatch")
    plan_rows = list(plan.get("results", []))
    report_rows = list(report.get("results", []))
    if report.get("status") != "INCOMPLETE_FAILURES_PRESERVED":
        errors.append("Source capture report is not an incomplete preserved result")
    if not plan_rows or len(plan_rows) != len(report_rows):
        errors.append("Capture plan/report populations differ or are empty")
    if report.get("planned_capture_count") != len(plan_rows):
        errors.append("Capture report planned count disagrees with the plan")
    if plan_item.get("record_count") != len(plan_rows):
        errors.append("Source release plan count disagrees with the plan")

    completed: list[dict[str, Any]] = []
    retry_rows: list[dict[str, Any]] = []
    for index, source in enumerate(plan_rows):
        if index >= len(report_rows):
            break
        row = report_rows[index]
        if _identity(row) != _identity(source):
            errors.append(f"Capture plan/report identity mismatch at row {index}")
            continue
        try:
            assert_archive_url(str(row["requested_archive_url"]))
            if "id_/" not in str(row["requested_archive_url"]):
                errors.append(f"Raw replay modifier missing at row {index}")
        except (KeyError, ValueError) as error:
            errors.append(f"Invalid archive URL at row {index}: {error}")
        target = Path(str(row.get("capture_path", "")))
        outcome = row.get("outcome")
        if outcome == "CAPTURED":
            if not target.is_file():
                errors.append(f"Completed capture is missing at row {index}")
                continue
            observed_bytes = target.stat().st_size
            observed_hash = sha256_file(target)
            if row.get("bytes") != observed_bytes or row.get("sha256") != observed_hash:
                errors.append(f"Completed capture byte/hash mismatch at row {index}")
                continue
            if (
                row.get("http_status") != 200
                or not str(row.get("content_type") or "").casefold().startswith("text/html")
                or row.get("error") is not None
            ):
                errors.append(f"Completed capture metadata is invalid at row {index}")
                continue
            completed.append(
                {
                    **_identity(row),
                    "bytes": observed_bytes,
                    "sha256": observed_hash,
                }
            )
        elif outcome in RETRY_OUTCOMES:
            if target.exists():
                errors.append(f"Retry row already has a capture target at row {index}")
            if not row.get("error") or row.get("bytes") is not None or row.get("sha256") is not None:
                errors.append(f"Retry row does not preserve a clean error at row {index}")
            retry_rows.append(
                {
                    **_identity(row),
                    "prior_outcome": outcome,
                    "prior_http_status": row.get("http_status"),
                    "prior_error": row.get("error"),
                }
            )
        else:
            errors.append(f"Unsupported capture outcome at row {index}: {outcome}")

    if not retry_rows:
        errors.append("Partial capture QA produced no missing/error rows")
    checks = qa.get("checks", {})
    expected_counts = {
        "planned_capture_count": len(plan_rows),
        "captured_count": len(completed),
        "failed_count": sum(row.get("outcome") == "FAILED" for row in report_rows),
        "not_attempted_count": sum(
            row.get("outcome") == "NOT_ATTEMPTED_AFTER_HTTP_429_STOP"
            for row in report_rows
        ),
    }
    for key, value in expected_counts.items():
        if checks.get(key) != value or report.get(key) != value:
            errors.append(f"Partial QA/report aggregate mismatch: {key}")
    captured_by_cohort = dict(
        Counter(
            str(row.get("cohort"))
            for row in report_rows
            if row.get("outcome") == "CAPTURED"
        )
    )
    if checks.get("captured_by_cohort") != captured_by_cohort or report.get("captured_by_cohort") != captured_by_cohort:
        errors.append("Partial QA/report captured-by-cohort aggregate mismatch")
    requests = report.get("network_request_count", -1)
    if requests < expected_counts["captured_count"] + expected_counts["failed_count"] or requests > len(plan_rows) * 4:
        errors.append("Capture network request count is outside the source bound")
    stopped_on_429 = any(row.get("http_status") == 429 for row in report_rows)
    if report.get("stopped_on_http_429") is not stopped_on_429 or checks.get("stopped_on_http_429") is not stopped_on_429:
        errors.append("HTTP 429 stop flag and source evidence disagree")

    try:
        report_created_at = parse_time(str(report["created_at"]))
        release_created_at = parse_time(created_at)
        release_not_before = parse_time(not_before)
        if release_not_before < report_created_at + timedelta(hours=24):
            errors.append("Retry not-before is less than 24 hours after partial report creation")
        if release_not_before < release_created_at:
            errors.append("Retry not-before predates retry-release creation")
    except (KeyError, TypeError, ValueError) as error:
        errors.append(str(error))
    partial_target = report_path.with_suffix(report_path.suffix + ".partial")
    if report_path.exists() or partial_target.exists():
        errors.append("Retry capture report target or partial already exists")
    if report_path.resolve() == capture_report_path:
        errors.append("Retry report must not overwrite the source partial report")
    if errors:
        raise ValueError(f"Capture retry release validation failed: {errors}")

    return {
        "release_id": RELEASE_ID,
        "created_at": created_at,
        "status": "FROZEN_EXACT_MISSING_ROWS_ARCHIVE_ONLY_RETRY_NOT_BEFORE_GATE",
        "inputs": {
            "independent_partial_capture_qa": {
                "path": str(partial_qa_path.resolve()),
                "sha256": sha256_file(partial_qa_path),
                "required_status": PARTIAL_QA_STATUS,
            },
            "source_capture_release": {
                "path": str(source_release_path),
                "sha256": source_release_hash,
            },
            "source_capture_release_qa": {
                "path": str(source_release_qa_path),
                "sha256": source_release_qa_hash,
            },
            "capture_plan": {
                "path": str(plan_path),
                "sha256": plan_hash,
            },
            "capture_report": {
                "path": str(capture_report_path),
                "sha256": capture_report_hash,
            },
        },
        "source_population_count": len(plan_rows),
        "completed_capture_count": len(completed),
        "retry_capture_count": len(retry_rows),
        "completed_capture_ledger": completed,
        "retry_rows": retry_rows,
        "execution_contract": {
            "not_before": not_before,
            "minimum_cooldown_seconds_after_partial_report": 86400.0,
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
            "completed_rows_are_immutable": True,
            "failed_rows_are_not_replaced": True,
            "output_overwrite_allowed": False,
        },
        "planned_output": {
            "path": str(report_path.resolve()),
            "report_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_CAPTURE_MISSING_ROW_RETRY_REPORT_V1",
        },
        "decision": {
            "archive_only_missing_row_retry_allowed_at_or_after_not_before": True,
            "candidate_live_domain_access_allowed": False,
            "text_extraction_allowed": False,
            "labeling_allowed": False,
            "validation_or_test_opening_allowed": False,
            "training_allowed": False,
            "model_scoring_allowed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--partial-qa", type=Path, required=True)
    parser.add_argument("--source-release", type=Path, required=True)
    parser.add_argument("--source-release-qa", type=Path, required=True)
    parser.add_argument("--capture-report", type=Path, required=True)
    parser.add_argument("--not-before", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite capture retry release")
    release = build_retry_release(
        partial_qa_path=args.partial_qa,
        source_release_path=args.source_release,
        source_release_qa_path=args.source_release_qa,
        capture_report_path=args.capture_report,
        not_before=args.not_before,
        report_path=args.report,
        created_at=args.created_at,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(
        json.dumps(
            {
                "release_id": RELEASE_ID,
                "retry_capture_count": release["retry_capture_count"],
                "output": str(args.output),
                "sha256": sha256_file(args.output),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
