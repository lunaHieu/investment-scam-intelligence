"""Independently audit every SEC/IAPD Wayback capture result and raw byte hash."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.build_sec_edgar_iapd_wayback_capture_release_v1 import RELEASE_ID
from scripts.execute_sec_edgar_iapd_wayback_capture_v1 import RELEASE_QA_STATUS
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def status_for(errors: list[str], captured: int, planned: int) -> str:
    if errors:
        return "FAIL"
    if planned > 0 and captured == planned:
        return "PASS_COMPLETE_TEXT_EXTRACTION_RELEASE_MAY_BE_PREPARED"
    return "PASS_PARTIAL_CAPTURE_RETRY_REQUIRED_TEXT_EXTRACTION_BLOCKED"


def verify(release_path: Path, release_qa_path: Path, report_path: Path) -> dict[str, Any]:
    release = load_object(release_path)
    release_qa = load_object(release_qa_path)
    report = load_object(report_path)
    errors: list[str] = []
    if release.get("release_id") != RELEASE_ID:
        errors.append("Unexpected capture release identity")
    if release_qa.get("status") != RELEASE_QA_STATUS or release_qa.get("release", {}).get("sha256") != sha256_file(release_path):
        errors.append("Capture release QA status or binding mismatch")
    if report.get("report_id") != release.get("planned_output", {}).get("report_id"):
        errors.append("Unexpected capture report identity")
    if report.get("release", {}).get("sha256") != sha256_file(release_path):
        errors.append("Capture report release hash mismatch")
    if report.get("release_qa", {}).get("sha256") != sha256_file(release_qa_path):
        errors.append("Capture report release-QA hash mismatch")
    plan_path = Path(str(release.get("inputs", {}).get("capture_plan", {}).get("path", "")))
    try:
        if sha256_file(plan_path) != release["inputs"]["capture_plan"]["sha256"]:
            errors.append("Capture plan hash mismatch")
        plan = load_object(plan_path)
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError) as error:
        plan = {}
        errors.append(f"Cannot read capture plan: {error}")
    planned = list(plan.get("results", []))
    results = list(report.get("results", []))
    if len(results) != len(planned) or report.get("planned_capture_count") != len(planned):
        errors.append("Capture result population changed")
    identity_keys = (
        "availability_plan_id", "shortlist_id", "cohort", "candidate_host",
        "candidate_url", "snapshot_timestamp", "snapshot_url",
        "requested_archive_url", "capture_path",
    )
    captured = failed = not_attempted = 0
    captured_by_cohort: Counter[str] = Counter()
    for index, source in enumerate(planned):
        if index >= len(results):
            break
        row = results[index]
        for key in identity_keys:
            if row.get(key) != source.get(key):
                errors.append(f"Plan/result mismatch at row {index}: {key}")
        outcome = row.get("outcome")
        target = Path(str(source.get("capture_path", "")))
        if outcome == "CAPTURED":
            captured += 1
            captured_by_cohort[str(row.get("cohort"))] += 1
            if not target.is_file():
                errors.append(f"Captured file is missing at row {index}")
                continue
            observed_bytes = target.stat().st_size
            observed_hash = sha256_file(target)
            if row.get("bytes") != observed_bytes or row.get("sha256") != observed_hash:
                errors.append(f"Captured byte/hash mismatch at row {index}")
            if row.get("http_status") != 200 or not str(row.get("content_type") or "").casefold().startswith("text/html"):
                errors.append(f"Captured HTTP/content metadata invalid at row {index}")
            if row.get("error") is not None:
                errors.append(f"Captured row retains an error at row {index}")
        elif outcome == "FAILED":
            failed += 1
            if target.exists():
                errors.append(f"Failed row unexpectedly has a raw file at row {index}")
            if not row.get("error") or any(row.get(key) is not None for key in ("bytes", "sha256")):
                errors.append(f"Failed row does not preserve a clean error at row {index}")
        elif outcome == "NOT_ATTEMPTED_AFTER_HTTP_429_STOP":
            not_attempted += 1
            if target.exists():
                errors.append(f"Unattempted row unexpectedly has a raw file at row {index}")
            if row.get("error") != "NOT_ATTEMPTED_AFTER_HTTP_429_STOP":
                errors.append(f"Unattempted row lacks the frozen stop reason at row {index}")
        else:
            errors.append(f"Unknown capture outcome at row {index}: {outcome}")
    aggregates = {
        "captured_count": captured,
        "failed_count": failed,
        "not_attempted_count": not_attempted,
        "captured_by_cohort": dict(captured_by_cohort),
    }
    for key, expected in aggregates.items():
        if report.get(key) != expected:
            errors.append(f"Capture report aggregate mismatch: {key}")
    if report.get("network_request_count", -1) < captured + failed or report.get("network_request_count", -1) > len(planned) * 4:
        errors.append("Capture network request count is outside the release bound")
    if report.get("stopped_on_http_429") is not any(row.get("http_status") == 429 for row in results):
        errors.append("HTTP 429 stop flag and evidence disagree")
    expected_report_status = "COMPLETE" if captured == len(planned) else "INCOMPLETE_FAILURES_PRESERVED"
    if report.get("status") != expected_report_status:
        errors.append("Capture report status disagrees with outcomes")
    status = status_for(errors, captured, len(planned))
    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_CAPTURE_RESULT_INDEPENDENT_QA_V1",
        "status": status,
        "inputs": {
            "release_sha256": sha256_file(release_path),
            "release_qa_sha256": sha256_file(release_qa_path),
            "report_sha256": sha256_file(report_path),
            "plan_sha256": release.get("inputs", {}).get("capture_plan", {}).get("sha256"),
        },
        "checks": {
            "membership_and_order_preserved": not any("Plan/result mismatch" in error or "population changed" in error for error in errors),
            "raw_byte_hashes_verified": not any("byte/hash mismatch" in error or "file is missing" in error for error in errors),
            "planned_capture_count": len(planned),
            "captured_count": captured,
            "captured_by_cohort": dict(captured_by_cohort),
            "failed_count": failed,
            "not_attempted_count": not_attempted,
            "stopped_on_http_429": report.get("stopped_on_http_429"),
        },
        "decision": {
            "capture_result_qa_passed": not errors,
            "text_extraction_release_may_be_prepared": status == "PASS_COMPLETE_TEXT_EXTRACTION_RELEASE_MAY_BE_PREPARED",
            "capture_retry_required": status == "PASS_PARTIAL_CAPTURE_RETRY_REQUIRED_TEXT_EXTRACTION_BLOCKED",
            "candidate_live_domain_access_allowed": False,
            "labeling_allowed": False,
            "validation_or_test_opening_allowed": False,
            "training_allowed": False,
        },
        "errors": errors,
        "safety_contract": {"network_operations": 0, "raw_files_modified": 0, "labels": 0, "model": 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-qa", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite capture result QA")
    result = verify(args.release, args.release_qa, args.report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
