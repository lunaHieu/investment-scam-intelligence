"""Recompute the canonical empty CDX payload and close A1 without a retry."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.verify_sec_edgar_iapd_wayback_alternate_snapshot_cdx_owner_override_result_v1 import verify as verify_v1
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


CANONICAL_EMPTY_CDX_PAYLOAD = b"[]\n"
CANONICAL_EMPTY_SHA256 = hashlib.sha256(CANONICAL_EMPTY_CDX_PAYLOAD).hexdigest()
PASS_STATUS = "PASS_OWNER_OVERRIDE_CANONICAL_EMPTY_CDX_RESPONSE_NO_ALTERNATE_QUARANTINE_REMAINS"


def verify(
    override_path: Path,
    override_qa_path: Path,
    report_path: Path,
    v1_result_qa_path: Path,
    *,
    require_frozen_output_path: bool = True,
) -> dict[str, Any]:
    errors: list[str] = []
    report = load_object(report_path)
    v1_qa = load_object(v1_result_qa_path)
    recomputed_v1 = verify_v1(
        override_path,
        override_qa_path,
        report_path,
        require_frozen_output_path=require_frozen_output_path,
    )
    if recomputed_v1.get("status") != "PASS_OWNER_OVERRIDE_CDX_FAILURE_PRESERVED_QUARANTINE_REMAINS" or recomputed_v1.get("errors") != []:
        errors.append("V1 result QA does not independently preserve the execution outcome")
    if v1_qa != recomputed_v1:
        errors.append("Stored V1 result QA differs from full recomputation")
    diagnostics = report.get("response_diagnostics", {})
    expected = {
        "http_status": 200,
        "content_type": "application/json",
        "response_bytes": len(CANONICAL_EMPTY_CDX_PAYLOAD),
        "response_sha256": CANONICAL_EMPTY_SHA256,
    }
    for key, value in expected.items():
        if diagnostics.get(key) != value:
            errors.append(f"CDX diagnostic does not match canonical empty JSON payload: {key}")
    if report.get("status") != "INCOMPLETE_ERROR_PRESERVED" or report.get("error") != "ValueError: CDX response must be a non-empty JSON table":
        errors.append("Report does not preserve the exact known empty-table parser limitation")
    if report.get("enumeration") is not None or report.get("network_request_count") != 1 or report.get("stopped_on_http_429") is not False:
        errors.append("Report request/enumeration state is inconsistent with a canonical empty response")
    if report.get("safety_contract", {}).get("archived_page_download_operations") != 0 or report.get("safety_contract", {}).get("candidate_live_domain_access_operations") != 0:
        errors.append("Execution safety counters changed")
    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_ALTERNATE_SNAPSHOT_CDX_OWNER_OVERRIDE_RESULT_QA_V2",
        "status": PASS_STATUS if not errors else "FAIL",
        "inputs": {
            "override_sha256": sha256_file(override_path),
            "override_qa_sha256": sha256_file(override_qa_path),
            "report_sha256": sha256_file(report_path),
            "v1_result_qa_sha256": sha256_file(v1_result_qa_path),
        },
        "checks": {
            "network_request_count": report.get("network_request_count"),
            "http_status": diagnostics.get("http_status"),
            "content_type": diagnostics.get("content_type"),
            "response_bytes": diagnostics.get("response_bytes"),
            "canonical_empty_payload_sha256_recomputed": CANONICAL_EMPTY_SHA256,
            "canonical_empty_payload_hash_matches": diagnostics.get("response_sha256") == CANONICAL_EMPTY_SHA256,
            "archived_page_downloads": 0,
        },
        "root_cause": {
            "category": "PARSER_DID_NOT_ACCEPT_VALID_ZERO_ROW_CDX_JSON",
            "network_failure": False,
            "rate_limit": False,
            "retry_needed": False,
            "explanation": "CDX returned HTTP 200 application/json with the exact three-byte canonical payload [] followed by newline; V1 required a non-empty table header and therefore preserved a ValueError instead of classifying zero eligible rows.",
        },
        "decision": {
            "a1_complete": not errors,
            "eligible_alternate_snapshot_found": False,
            "same_query_retry_allowed": False,
            "separate_capture_release_may_be_prepared": False,
            "quarantine_remains": True,
            "original_review_population_may_be_mutated": False,
            "training_allowed": False,
        },
        "errors": errors,
        "safety_contract": {"network_operations": 0, "candidate_domain_access_operations": 0, "archived_page_downloads": 0, "captures": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--override", type=Path, required=True)
    parser.add_argument("--override-qa", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--v1-result-qa", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    if args.output.exists() or partial.exists():
        raise FileExistsError("Refusing to overwrite owner-override CDX V2 result QA")
    result = verify(args.override, args.override_qa, args.report, args.v1_result_qa)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
