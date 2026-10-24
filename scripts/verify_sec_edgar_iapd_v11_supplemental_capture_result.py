"""Independently verify every V11 supplemental capture byte and hash."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.build_sec_edgar_iapd_v11_supplemental_capture_release import RELEASE_QA_STATUS
from scripts.build_sec_edgar_iapd_v11_supplemental_capture_release import RELEASE_ID
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def verify(release_path: Path, release_qa_path: Path, report_path: Path) -> dict[str, Any]:
    release = load_object(release_path)
    release_qa = load_object(release_qa_path)
    report = load_object(report_path)
    errors: list[str] = []
    if release.get("release_id") != RELEASE_ID:
        errors.append("Unexpected V11 supplemental release identity")
    if release_qa.get("status") != RELEASE_QA_STATUS or release_qa.get("release", {}).get("sha256") != sha256_file(release_path):
        errors.append("Supplemental release QA status or hash binding mismatch")
    if report.get("report_id") != release.get("planned_output", {}).get("report_id"):
        errors.append("Unexpected supplemental capture report identity")
    if report.get("release", {}).get("sha256") != sha256_file(release_path):
        errors.append("Supplemental capture report release hash mismatch")
    if report.get("release_qa", {}).get("sha256") != sha256_file(release_qa_path):
        errors.append("Supplemental capture report release-QA hash mismatch")
    plan_path = Path(str(release.get("inputs", {}).get("capture_plan", {}).get("path", "")))
    try:
        if sha256_file(plan_path) != release["inputs"]["capture_plan"]["sha256"]:
            errors.append("Supplemental capture plan hash mismatch")
        plan = load_object(plan_path)
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError) as error:
        plan = {}
        errors.append(f"Cannot read supplemental capture plan: {error}")
    planned = list(plan.get("results", []))
    results = list(report.get("results", []))
    if len(results) != len(planned) or report.get("planned_capture_count") != len(planned):
        errors.append("Supplemental capture result population changed")
    identity_keys = ("availability_plan_id", "shortlist_id", "cohort", "candidate_host", "candidate_url", "snapshot_timestamp", "snapshot_url", "requested_archive_url", "capture_path")
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
            if row.get("bytes") != target.stat().st_size or row.get("sha256") != sha256_file(target):
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
            if row.get("http_status") == 429 and not row.get("diagnostics"):
                errors.append(f"HTTP 429 diagnostics missing at row {index}")
        elif outcome == "NOT_ATTEMPTED_AFTER_HTTP_429_STOP":
            not_attempted += 1
            if target.exists() or row.get("error") != "NOT_ATTEMPTED_AFTER_HTTP_429_STOP":
                errors.append(f"Unattempted row is not preserved at row {index}")
        else:
            errors.append(f"Unknown supplemental capture outcome at row {index}: {outcome}")
    aggregates = {"captured_count": captured, "failed_count": failed, "not_attempted_count": not_attempted, "captured_by_cohort": dict(captured_by_cohort)}
    for key, expected in aggregates.items():
        if report.get(key) != expected:
            errors.append(f"Supplemental report aggregate mismatch: {key}")
    if report.get("network_request_count", -1) < captured + failed or report.get("network_request_count", -1) > len(planned) * 4:
        errors.append("Supplemental network request count is outside release bound")
    if report.get("stopped_on_http_429") is not any(row.get("http_status") == 429 for row in results):
        errors.append("HTTP 429 stop flag and evidence disagree")
    expected_status = "COMPLETE" if captured == len(planned) else "INCOMPLETE_FAILURES_PRESERVED"
    if report.get("status") != expected_status:
        errors.append("Supplemental report status disagrees with outcomes")
    qa_status = "PASS_COMPLETE_V11_SUPPLEMENTAL_CAPTURE_TEXT_EXTRACTION_MAY_BE_PREPARED" if not errors and captured == len(planned) else "PASS_PARTIAL_V11_SUPPLEMENTAL_CAPTURE_RETRY_REQUIRED_TEXT_EXTRACTION_BLOCKED" if not errors else "FAIL"
    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_V11_SUPPLEMENTAL_CAPTURE_RESULT_INDEPENDENT_QA_V1",
        "status": qa_status,
        "inputs": {"release_sha256": sha256_file(release_path), "release_qa_sha256": sha256_file(release_qa_path), "report_sha256": sha256_file(report_path), "plan_sha256": release.get("inputs", {}).get("capture_plan", {}).get("sha256")},
        "checks": {"membership_and_order_preserved": not any("Plan/result mismatch" in e or "population changed" in e for e in errors), "raw_byte_hashes_verified": not any("byte/hash mismatch" in e or "file is missing" in e for e in errors), "planned_capture_count": len(planned), "captured_count": captured, "captured_by_cohort": dict(captured_by_cohort), "failed_count": failed, "not_attempted_count": not_attempted, "stopped_on_http_429": report.get("stopped_on_http_429")},
        "decision": {"capture_result_qa_passed": not errors, "text_extraction_release_may_be_prepared": qa_status == "PASS_COMPLETE_V11_SUPPLEMENTAL_CAPTURE_TEXT_EXTRACTION_MAY_BE_PREPARED", "capture_retry_required": qa_status == "PASS_PARTIAL_V11_SUPPLEMENTAL_CAPTURE_RETRY_REQUIRED_TEXT_EXTRACTION_BLOCKED", "candidate_live_domain_access_allowed": False, "labeling_allowed": False, "validation_or_test_opening_allowed": False, "training_allowed": False},
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
        raise FileExistsError("Refusing to overwrite V11 supplemental capture result QA")
    result = verify(args.release, args.release_qa, args.report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
