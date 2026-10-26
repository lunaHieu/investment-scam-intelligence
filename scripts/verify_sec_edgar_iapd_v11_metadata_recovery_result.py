"""Independently verify the V11 metadata-recovery capture result."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse
from typing import Any

from scripts.build_sec_edgar_iapd_v11_metadata_recovery_release import (
    EXPECTED_IDS,
    RELEASE_ID,
    RELEASE_QA_STATUS,
)
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def _qa_release_hash(qa: dict[str, Any]) -> str | None:
    return qa.get("release_sha256") or qa.get("release", {}).get("sha256")


def _is_archive_url(value: Any) -> bool:
    try:
        parsed = urlparse(str(value))
    except ValueError:
        return False
    return parsed.scheme == "https" and parsed.hostname == "web.archive.org"


def verify(release_path: Path, release_qa_path: Path, report_path: Path) -> dict[str, Any]:
    release = load_object(release_path)
    release_qa = load_object(release_qa_path)
    report = load_object(report_path)
    errors: list[str] = []
    if release.get("release_id") != RELEASE_ID:
        errors.append("Unexpected V11 metadata-recovery release identity")
    if release_qa.get("status") != RELEASE_QA_STATUS or _qa_release_hash(release_qa) != sha256_file(release_path):
        errors.append("Metadata-recovery release QA status or hash binding mismatch")
    if report.get("report_id") != release.get("planned_output", {}).get("report_id"):
        errors.append("Unexpected metadata-recovery report identity")
    if report.get("release", {}).get("sha256") != sha256_file(release_path):
        errors.append("Metadata-recovery report release hash mismatch")
    if report.get("release_qa", {}).get("sha256") != sha256_file(release_qa_path):
        errors.append("Metadata-recovery report release-QA hash mismatch")

    plan_path = Path(str(release.get("inputs", {}).get("recovery_plan", {}).get("path", "")))
    try:
        if sha256_file(plan_path) != release["inputs"]["recovery_plan"]["sha256"]:
            errors.append("Metadata-recovery plan hash mismatch")
        plan = load_object(plan_path)
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError) as error:
        plan = {}
        errors.append(f"Cannot read metadata-recovery plan: {error}")

    planned = list(plan.get("results", []))
    expected_plan_ids = list(EXPECTED_IDS)
    if [row.get("availability_plan_id") for row in planned] != expected_plan_ids:
        errors.append("Metadata-recovery plan identity/order changed")
    results = list(report.get("results", []))
    if len(results) != len(planned) or report.get("planned_capture_count") != len(planned):
        errors.append("Metadata-recovery result population changed")

    identity_keys = (
        "availability_plan_id", "shortlist_id", "cohort", "candidate_host", "candidate_url",
        "snapshot_timestamp", "snapshot_url", "requested_archive_url", "capture_path",
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
                errors.append(f"Captured recovery file is missing at row {index}")
                continue
            if row.get("bytes") != target.stat().st_size or row.get("sha256") != sha256_file(target):
                errors.append(f"Captured recovery byte/hash mismatch at row {index}")
            if row.get("http_status") != 200 or not str(row.get("content_type") or "").casefold().startswith("text/html"):
                errors.append(f"Captured recovery HTTP/content metadata invalid at row {index}")
            if not _is_archive_url(row.get("final_archive_url")):
                errors.append(f"Captured recovery final URL is not archive-only at row {index}")
            if not isinstance(row.get("redirect_count"), int) or row.get("redirect_count") < 0:
                errors.append(f"Captured recovery redirect count invalid at row {index}")
            if not isinstance(row.get("diagnostics"), dict):
                errors.append(f"Captured recovery diagnostics missing at row {index}")
            if row.get("error") is not None:
                errors.append(f"Captured recovery row retains an error at row {index}")
        elif outcome == "FAILED":
            failed += 1
            if target.exists():
                errors.append(f"Failed recovery row unexpectedly has a raw file at row {index}")
            if not row.get("error") or any(row.get(key) is not None for key in ("bytes", "sha256")):
                errors.append(f"Failed recovery row does not preserve a clean error at row {index}")
            if row.get("http_status") == 429 and not row.get("diagnostics"):
                errors.append(f"HTTP 429 diagnostics missing at row {index}")
        elif outcome == "NOT_ATTEMPTED_AFTER_HTTP_429_STOP":
            not_attempted += 1
            if target.exists() or row.get("error") != "NOT_ATTEMPTED_AFTER_HTTP_429_STOP":
                errors.append(f"Unattempted recovery row is not preserved at row {index}")
        else:
            errors.append(f"Unknown metadata-recovery outcome at row {index}: {outcome}")

    aggregates = {
        "captured_count": captured,
        "failed_count": failed,
        "not_attempted_count": not_attempted,
        "captured_by_cohort": dict(captured_by_cohort),
    }
    for key, expected in aggregates.items():
        if report.get(key) != expected:
            errors.append(f"Metadata-recovery report aggregate mismatch: {key}")
    request_count = report.get("network_request_count", -1)
    if not isinstance(request_count, int) or request_count < captured + failed or request_count > len(planned) * 4:
        errors.append("Metadata-recovery network request count is outside release bound")
    if report.get("stopped_on_http_429") is not any(row.get("http_status") == 429 for row in results):
        errors.append("HTTP 429 stop flag and evidence disagree")
    expected_status = "COMPLETE" if captured == len(planned) else "INCOMPLETE_FAILURES_PRESERVED"
    if report.get("status") != expected_status:
        errors.append("Metadata-recovery report status disagrees with outcomes")

    safety = report.get("safety_contract", {})
    expected_safety = {
        "candidate_live_domain_access_operations": 0,
        "only_web_archive_host_accessed": True,
        "raw_replay_modifier_used": True,
        "automatic_external_redirect_following": False,
        "labels_created": 0,
        "model_operations": 0,
        "training_allowed": False,
    }
    for key, expected in expected_safety.items():
        if safety.get(key) != expected:
            errors.append(f"Recovery safety contract mismatch: {key}")

    complete = not errors and captured == len(planned)
    qa_status = "PASS_COMPLETE_V11_METADATA_RECOVERY_CAPTURE_METADATA_VERIFIED_EXACT_TEXT_RELEASE_MAY_BE_PREPARED" if complete else "PASS_PARTIAL_V11_METADATA_RECOVERY_CAPTURE_RETRY_REQUIRED_TEXT_EXTRACTION_BLOCKED" if not errors else "FAIL"
    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_V11_METADATA_RECOVERY_RESULT_INDEPENDENT_QA_V1",
        "status": qa_status,
        "inputs": {"release_sha256": sha256_file(release_path), "release_qa_sha256": sha256_file(release_qa_path), "report_sha256": sha256_file(report_path), "plan_sha256": release.get("inputs", {}).get("recovery_plan", {}).get("sha256")},
        "checks": {"membership_and_order_preserved": not any("Plan/result mismatch" in e or "population changed" in e for e in errors), "raw_byte_hashes_verified": not any("byte/hash mismatch" in e or "file is missing" in e for e in errors), "response_metadata_verified": not any("metadata" in e or "final URL" in e or "redirect count" in e or "diagnostics" in e for e in errors), "planned_capture_count": len(planned), "captured_count": captured, "captured_by_cohort": dict(captured_by_cohort), "failed_count": failed, "not_attempted_count": not_attempted, "stopped_on_http_429": report.get("stopped_on_http_429")},
        "decision": {"capture_result_qa_passed": not errors, "text_extraction_release_may_be_prepared": complete, "capture_retry_required": qa_status == "PASS_PARTIAL_V11_METADATA_RECOVERY_CAPTURE_RETRY_REQUIRED_TEXT_EXTRACTION_BLOCKED", "candidate_live_domain_access_allowed": False, "labeling_allowed": False, "validation_or_test_opening_allowed": False, "training_allowed": False},
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
        raise FileExistsError("Refusing to overwrite metadata-recovery result QA")
    result = verify(args.release, args.release_qa, args.report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
