"""Verify unresolved-only SEC/IAPD Wayback availability retry V2."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.verify_sec_edgar_iapd_wayback_availability_result_v1 import read_jsonl, valid_snapshot_url
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def verify(release_path: Path, v1_path: Path, v2_path: Path) -> dict[str, Any]:
    release = load_object(release_path)
    v1 = load_object(v1_path)
    v2 = load_object(v2_path)
    plan = read_jsonl(Path(release["inputs"]["availability_plan"]["path"]))
    errors: list[str] = []
    if v2.get("report_id") != "ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_AVAILABILITY_REPORT_V2":
        errors.append("Unexpected V2 report identity")
    if v2.get("release_sha256") != sha256_file(release_path) or v2.get("parent_report_sha256") != sha256_file(v1_path):
        errors.append("V2 release or parent hash mismatch")
    v1_by_id = {row["availability_plan_id"]: row for row in v1["results"]}
    v2_by_id = {row["availability_plan_id"]: row for row in v2["results"]}
    plan_ids = [row["availability_plan_id"] for row in plan]
    if list(v2_by_id) != plan_ids or set(v1_by_id) != set(v2_by_id):
        errors.append("V2 membership/order changed")
    prior_resolved = {key for key, row in v1_by_id.items() if row["error"] is None}
    prior_unresolved = set(v1_by_id) - prior_resolved
    for key in prior_resolved:
        if canonical(v1_by_id[key]) != canonical(v2_by_id[key]):
            errors.append(f"Resolved V1 result changed: {key}")
    retried = [str(value) for value in v2.get("retried_availability_plan_ids", [])]
    if not set(retried).issubset(prior_unresolved) or len(retried) != v2.get("network_request_count_this_attempt"):
        errors.append("V2 retried a resolved row or retry count changed")
    available = unavailable = unresolved = 0
    for key in plan_ids:
        row = v2_by_id[key]
        if row["error"] is not None:
            unresolved += 1
            if row["available"] is not None:
                errors.append(f"Unresolved V2 row has availability: {key}")
        elif row["available"] is True:
            available += 1
            if row["snapshot_http_status"] != "200" or not valid_snapshot_url(str(row["snapshot_url"]), str(row["snapshot_timestamp"])):
                errors.append(f"Invalid available V2 row: {key}")
        elif row["available"] is False:
            unavailable += 1
            if any(row[field] is not None for field in ("snapshot_timestamp", "snapshot_url", "snapshot_http_status")):
                errors.append(f"Unavailable V2 row retains evidence: {key}")
        else:
            errors.append(f"Resolved V2 row lacks availability: {key}")
    for field, value in (("available_snapshot_count", available), ("unavailable_snapshot_count", unavailable), ("unresolved_error_count", unresolved), ("requested_candidate_count", len(plan))):
        if v2.get(field) != value:
            errors.append(f"V2 aggregate mismatch: {field}")
    if v2.get("cumulative_network_request_count") != v1.get("network_request_count") + v2.get("network_request_count_this_attempt"):
        errors.append("V2 cumulative request count mismatch")
    if v2.get("stopped_on_http_429") is not True or not any("HTTP 429" in str(row["error"]) for row in v2["results"]):
        errors.append("V2 429 stop was not preserved")
    expected_safety = {"candidate_live_domain_access_operations": 0, "only_archive_availability_hosts_accessed": True, "archived_page_download_operations": 0, "artifact_captures": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False}
    if v2.get("safety_contract") != expected_safety:
        errors.append("V2 safety contract changed")
    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_RESULT_INDEPENDENT_QA_V2",
        "status": "PASS_PARTIAL_RATE_LIMIT_PRESERVED_FURTHER_RETRY_DEFERRED" if not errors else "FAIL",
        "inputs": {"release_sha256": sha256_file(release_path), "v1_sha256": sha256_file(v1_path), "v2_sha256": sha256_file(v2_path)},
        "checks": {"membership_preserved": set(v1_by_id) == set(v2_by_id) == set(plan_ids), "resolved_v1_results_preserved": not any("Resolved V1 result changed" in error for error in errors), "retried_only_prior_unresolved": set(retried).issubset(prior_unresolved), "resolved_results": available + unavailable, "available_results": available, "unavailable_results": unavailable, "unresolved_results": unresolved, "network_requests_v1": v1["network_request_count"], "network_requests_v2": v2["network_request_count_this_attempt"], "cumulative_network_requests": v2["cumulative_network_request_count"], "further_immediate_retry_allowed": False},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "candidate_domain_access_operations": 0, "archived_page_downloads": 0, "captures": 0, "labels": 0, "model": 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--v1", type=Path, required=True)
    parser.add_argument("--v2", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Refusing to overwrite V2 QA")
    result = verify(args.release, args.v1, args.v2)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
