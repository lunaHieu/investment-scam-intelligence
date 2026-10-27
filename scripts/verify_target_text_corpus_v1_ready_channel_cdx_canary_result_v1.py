"""Independently verify the ready-channel CDX metadata canary result."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.execute_target_text_corpus_v1_ready_channel_cdx_canary_v1 import (
    EXECUTOR,
    parse_metadata,
)
from scripts.verify_target_text_corpus_v1_ready_channel_cdx_canary_release_v1 import (
    PASS_STATUS,
    verify as verify_release,
)
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import (
    load_object,
    sha256_file,
)


QA_ID = "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_CDX_CANARY_RESULT_QA_V1"


def verify(release_path: Path, release_qa_path: Path, report_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        release = load_object(release_path)
        release_qa = load_object(release_qa_path)
        report = load_object(report_path)
    except Exception as error:
        return {"verification_id": QA_ID, "status": "FAIL", "errors": [f"Input load failed: {type(error).__name__}: {error}"]}
    checked = verify_release(release_path, require_output_absent=False)
    if checked.get("status") != PASS_STATUS or checked.get("errors"):
        errors.append("Frozen ready-channel CDX canary release no longer verifies")
    if release_qa.get("status") != PASS_STATUS or release_qa.get("errors") != []:
        errors.append("Frozen ready-channel CDX canary release QA is not PASS")
    if release_qa.get("release", {}).get("sha256") != sha256_file(release_path):
        errors.append("Ready-channel CDX canary release QA binding mismatch")
    if Path(release["planned_output"]["path"]) != report_path:
        errors.append("Ready-channel CDX canary report is not the frozen output")
    if report_path.with_suffix(report_path.suffix + ".partial").exists():
        errors.append("Ready-channel CDX canary partial journal remains")
    if report.get("executor") != EXECUTOR:
        errors.append("Ready-channel CDX canary executor identity changed")
    if report.get("release_sha256") != sha256_file(release_path) or report.get("release_qa_sha256") != sha256_file(release_qa_path):
        errors.append("Ready-channel CDX canary report binding changed")
    if report.get("target_availability_plan_id") != release["target_record"]["availability_plan_id"]:
        errors.append("Ready-channel CDX canary target identity changed")
    if report.get("network_request_count") != 1:
        errors.append("Ready-channel CDX canary did not use exactly one request")

    raw_info = report.get("raw_response")
    raw_path = Path(release["planned_output"]["raw_response_path"])
    raw_bytes: bytes | None = None
    if raw_info is None:
        if raw_path.exists():
            errors.append("Unexpected raw canary response exists")
    else:
        if Path(str(raw_info.get("path"))) != raw_path or not raw_path.is_file():
            errors.append("Raw canary response path is missing or changed")
        else:
            raw_bytes = raw_path.read_bytes()
            if len(raw_bytes) != raw_info.get("bytes") or sha256_file(raw_path) != raw_info.get("sha256"):
                errors.append("Raw canary response byte/hash verification failed")

    status = report.get("status")
    parsed = report.get("enumeration")
    valid = status in {
        "COMPLETE_VALID_CDX_CANARY_WITH_ELIGIBLE_METADATA",
        "COMPLETE_VALID_CDX_CANARY_EMPTY_NO_ELIGIBLE_SNAPSHOT",
    }
    recomputed: dict[str, Any] | None = None
    if valid:
        if raw_bytes is None or report.get("error") is not None:
            errors.append("Valid canary result lacks raw response or retains an error")
        else:
            try:
                recomputed = parse_metadata(raw_bytes, release)
            except Exception as error:
                errors.append(f"Canary metadata recomputation failed: {type(error).__name__}: {error}")
            if recomputed != parsed:
                errors.append("Canary metadata result is not independently reproducible")
    elif status == "INCOMPLETE_HTTP_429_ARCHIVE_PROVIDER_CIRCUIT_OPEN":
        if report.get("stopped_on_http_429") is not True or report.get("response_diagnostics", {}).get("http_status") != 429:
            errors.append("Canary HTTP 429 branch lacks preserved diagnostics")
    elif status == "INCOMPLETE_INVALID_CONTENT_PRESERVED_OFFLINE_RECONCILIATION_REQUIRED":
        if raw_bytes is None or not isinstance(report.get("error"), str):
            errors.append("Canary invalid-content branch did not preserve bytes and error")
    elif status == "INCOMPLETE_ERROR_PRESERVED_CDX_PATH_QUARANTINED":
        if not isinstance(report.get("error"), str):
            errors.append("Canary error branch did not preserve an error")
    else:
        errors.append("Unexpected ready-channel CDX canary result status")

    decision = report.get("decision", {})
    if decision.get("bulk_cdx_release_may_be_prepared") is not valid:
        errors.append("Canary bulk-release decision disagrees with valid metadata result")
    if decision.get("archive_provider_branch_closed") is not (status == "INCOMPLETE_HTTP_429_ARCHIVE_PROVIDER_CIRCUIT_OPEN"):
        errors.append("Canary provider-circuit decision disagrees with result")
    for field in ("automatic_cascade_allowed", "capture_authorized", "labeling_allowed", "training_allowed"):
        if decision.get(field) is not False:
            errors.append(f"Canary result opened forbidden decision: {field}")

    if errors:
        qa_status = "FAIL"
    elif status == "COMPLETE_VALID_CDX_CANARY_WITH_ELIGIBLE_METADATA":
        qa_status = "PASS_CDX_CANARY_VALID_BULK_RELEASE_MAY_BE_PREPARED"
    elif status == "COMPLETE_VALID_CDX_CANARY_EMPTY_NO_ELIGIBLE_SNAPSHOT":
        qa_status = "PASS_CDX_CANARY_EMPTY_BULK_RELEASE_MAY_BE_PREPARED_EXCLUDING_CANARY"
    elif status == "INCOMPLETE_HTTP_429_ARCHIVE_PROVIDER_CIRCUIT_OPEN":
        qa_status = "PASS_CDX_CANARY_HTTP_429_PROVIDER_BRANCH_CLOSED"
    elif status == "INCOMPLETE_INVALID_CONTENT_PRESERVED_OFFLINE_RECONCILIATION_REQUIRED":
        qa_status = "PASS_CDX_CANARY_INVALID_CONTENT_OFFLINE_RECONCILIATION_REQUIRED"
    else:
        qa_status = "PASS_CDX_CANARY_ERROR_CDX_PATH_QUARANTINED"
    return {
        "verification_id": QA_ID,
        "status": qa_status,
        "inputs": {
            "release_sha256": sha256_file(release_path),
            "release_qa_sha256": sha256_file(release_qa_path),
            "report_sha256": sha256_file(report_path),
        },
        "checks": {
            "target_rows": 1,
            "network_request_count": report.get("network_request_count"),
            "raw_response_hash_verified": raw_bytes is not None and not errors,
            "metadata_recomputed": recomputed == parsed if valid else False,
            "stopped_on_http_429": report.get("stopped_on_http_429"),
            "archived_page_downloads": 0,
        },
        "decision": {
            "bulk_cdx_release_may_be_prepared": valid and not errors,
            "archive_provider_branch_closed": status == "INCOMPLETE_HTTP_429_ARCHIVE_PROVIDER_CIRCUIT_OPEN" and not errors,
            "capture_authorized": False,
            "labeling_allowed": False,
            "training_allowed": False,
        },
        "errors": errors,
        "safety_contract": {
            "network_operations": 0,
            "candidate_domain_access_operations": 0,
            "archived_page_downloads": 0,
            "captures": 0,
            "labels_created": 0,
            "model_operations": 0,
            "training_allowed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-qa", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    if args.output.exists() or partial.exists():
        raise FileExistsError("Refusing to overwrite ready-channel CDX canary result QA")
    result = verify(args.release, args.release_qa, args.report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
