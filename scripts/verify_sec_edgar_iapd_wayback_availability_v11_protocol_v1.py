"""Verify the offline exact-two-row SEC/IAPD availability V11 protocol."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.retry_sec_edgar_iapd_wayback_availability_v4 import read_jsonl
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import (
    load_object,
    sha256_file,
)


PROTOCOL_ID = "ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_V11_PROTOCOL_V1"
PASS_STATUS = "PASS_FROZEN_EXACT_TWO_HOLDOUT_ROWS_TOOLING_READY_RELEASE_REQUIRED"
EXPECTED_IDS = ["TTCV1_EDGAR_AVAIL_HOLDOUT_011", "TTCV1_EDGAR_AVAIL_HOLDOUT_018"]


def verify(protocol_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        protocol = load_object(protocol_path)
    except Exception as error:
        return {
            "verification_id": "ISI_SEC_EDGAR_IAPD_AVAILABILITY_V11_PROTOCOL_QA_V1",
            "status": "FAIL",
            "errors": [f"Protocol loading failed: {type(error).__name__}: {error}"],
        }
    root = protocol_path.resolve().parents[1]
    if protocol.get("protocol_id") != PROTOCOL_ID:
        errors.append("Unexpected V11 protocol identity")
    if protocol.get("status") != "FROZEN_OFFLINE_TOOLING_ONLY_CONCRETE_RELEASE_REQUIRED":
        errors.append("Unexpected V11 protocol status")
    for item in protocol.get("basis", []):
        path = root / item["path"]
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            errors.append(f"V11 protocol basis mismatch: {item['path']}")
    for role, item in protocol.get("inputs", {}).items():
        path = Path(item["path"]) if item.get("absolute", False) else root / item["path"]
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            errors.append(f"V11 protocol input mismatch: {role}")

    v10 = load_object(Path(protocol["inputs"]["availability_report_v10"]["path"]))
    qa = load_object(Path(protocol["inputs"]["independent_qa_v10"]["path"]))
    plan = read_jsonl(Path(protocol["inputs"]["availability_plan"]["path"]))
    if qa.get("status") != "PASS_PARTIAL_ERRORS_PRESERVED_CAPTURE_PLAN_BLOCKED":
        errors.append("V10 independent QA status changed")
    if v10.get("status") != "INCOMPLETE_ERRORS_PRESERVED" or v10.get("stopped_on_http_429") is not True:
        errors.append("V10 partial/HTTP-429 outcome changed")
    plan_ids = [row["availability_plan_id"] for row in plan]
    v10_rows = v10.get("results", [])
    if [row.get("availability_plan_id") for row in v10_rows] != plan_ids:
        errors.append("V10 result membership/order differs from the frozen plan")
    unresolved = [row for row in v10_rows if row.get("error") is not None]
    unresolved_ids = [row["availability_plan_id"] for row in unresolved]
    if unresolved_ids != EXPECTED_IDS:
        errors.append("V11 exact unresolved identity/order changed")
    if any(row.get("cohort") != "EXTERNAL_HOLDOUT" for row in unresolved):
        errors.append("V11 contains a non-holdout row")
    if protocol.get("ordered_retry_rows") != [
        {
            key: row[key]
            for key in (
                "availability_plan_id",
                "shortlist_id",
                "cohort",
                "candidate_host",
                "candidate_url",
                "query_timestamp",
            )
        }
        for row in unresolved
    ]:
        errors.append("V11 frozen retry rows differ from the verified V10 errors")
    if protocol.get("parent_outcome_contract") != {
        "total_rows": 115,
        "resolved_rows": 113,
        "available_rows": 58,
        "unavailable_rows": 55,
        "unresolved_rows": 2,
        "external_holdout_unresolved_rows": 2,
        "cumulative_network_requests": 168,
        "resolved_rows_must_remain_byte_equivalent": True,
    }:
        errors.append("V11 parent outcome contract changed")

    contract = protocol.get("network_contract", {})
    if contract.get("endpoint") != "https://archive.org/wayback/available":
        errors.append("V11 availability endpoint changed")
    if set(contract.get("allowed_network_hosts", [])) != {"archive.org", "web.archive.org"}:
        errors.append("V11 archive host allowlist changed")
    if float(contract.get("minimum_delay_seconds", 0)) < 60.0:
        errors.append("V11 pacing is below 60 seconds")
    if contract.get("maximum_logical_attempts_per_row") != 1:
        errors.append("V11 row attempt budget changed")
    if contract.get("maximum_retry_rows") != 2:
        errors.append("V11 retry population bound changed")
    if contract.get("descriptive_user_agent") != (
        "ISI-Research/2.0 (gpt-5; https://github.com/lunaHieu/investment-scam-intelligence)"
    ):
        errors.append("V11 descriptive User-Agent changed")
    if contract.get("preserved_response_headers") != [
        "Retry-After",
        "Date",
        "Server",
        "Content-Type",
        "X-Archive-Wayback-Runtime-Error",
    ]:
        errors.append("V11 diagnostic header set changed")
    for flag in (
        "https_only",
        "stop_on_http_429",
        "errors_are_preserved",
        "errors_are_not_interpreted_as_no_snapshot",
        "partial_journal_reserved_before_network",
    ):
        if contract.get(flag) is not True:
            errors.append(f"V11 required network guard changed: {flag}")
    for flag in ("automatic_external_redirect_following", "partial_journal_auto_resume_allowed", "output_overwrite_allowed"):
        if contract.get(flag) is not False:
            errors.append(f"V11 fail-closed network guard changed: {flag}")

    release_contract = protocol.get("future_release_contract", {})
    if release_contract.get("concrete_release_required") is not True:
        errors.append("V11 concrete release requirement is missing")
    if release_contract.get("minimum_cooldown_seconds_after_latest_archive_request") != 86400:
        errors.append("V11 future release cooldown changed")
    if release_contract.get("must_bind_latest_actual_archive_request") is not True:
        errors.append("V11 latest-request binding is missing")
    if release_contract.get("cdx_result_if_executed_must_precede_release_freeze") is not True:
        errors.append("V11 does not require the future CDX result before release freeze")

    decision = protocol.get("decision", {})
    for field in (
        "network_execution_allowed_by_protocol",
        "candidate_live_domain_access_allowed",
        "archived_page_download_allowed",
        "capture_plan_mutation_allowed",
        "labeling_allowed",
        "validation_or_test_opening_allowed",
        "model_scoring_allowed",
        "training_allowed",
    ):
        if decision.get(field) is not False:
            errors.append(f"Forbidden V11 protocol decision opened: {field}")
    if decision.get("tooling_may_be_prepared_offline") is not True:
        errors.append("V11 offline tooling preparation is not authorized")

    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_AVAILABILITY_V11_PROTOCOL_QA_V1",
        "status": PASS_STATUS if not errors else "FAIL",
        "protocol": {"path": str(protocol_path.resolve()), "sha256": sha256_file(protocol_path)},
        "checks": {
            "plan_rows": len(plan),
            "resolved_parent_rows": 113,
            "ordered_retry_ids": unresolved_ids,
            "retry_cohort": "EXTERNAL_HOLDOUT",
            "minimum_delay_seconds": contract.get("minimum_delay_seconds"),
            "concrete_release_required": release_contract.get("concrete_release_required"),
            "network_execution_allowed": False,
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
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.protocol)
    if args.output:
        partial = args.output.with_suffix(args.output.suffix + ".partial")
        if args.output.exists() or partial.exists():
            raise FileExistsError("Refusing to overwrite V11 protocol QA")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
