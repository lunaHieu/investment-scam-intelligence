"""Independently verify the SEC/IAPD Wayback availability retry V4 result."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.verify_sec_edgar_iapd_wayback_availability_result_v1 import read_jsonl, valid_snapshot_url
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


EXPECTED_SAFETY = {
    "candidate_live_domain_access_operations": 0,
    "only_archive_availability_hosts_accessed": True,
    "archived_page_download_operations": 0,
    "artifact_captures": 0,
    "labels_created": 0,
    "model_operations": 0,
    "training_allowed": False,
}


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Result timestamp must include a timezone")
    return parsed


def pass_status(unresolved: int) -> str:
    return "PASS_COMPLETE_CAPTURE_PLAN_MAY_BE_PREPARED" if unresolved == 0 else "PASS_PARTIAL_ERRORS_PRESERVED_CAPTURE_PLAN_BLOCKED"


def verify(release_path: Path, v3_path: Path, v4_path: Path) -> dict[str, Any]:
    release = load_object(release_path)
    v3 = load_object(v3_path)
    v4 = load_object(v4_path)
    plan = read_jsonl(Path(release["inputs"]["availability_plan"]["path"]))
    errors: list[str] = []
    if v4.get("report_id") != "ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_AVAILABILITY_REPORT_V4":
        errors.append("Unexpected V4 report identity")
    if v4.get("release_sha256") != sha256_file(release_path) or v4.get("parent_report_sha256") != sha256_file(v3_path):
        errors.append("V4 release or parent hash mismatch")
    if v4.get("plan_sha256") != sha256_file(Path(release["inputs"]["availability_plan"]["path"])):
        errors.append("V4 plan hash mismatch")
    try:
        if parse_time(str(v4.get("created_at"))) < parse_time(release["cooldown_contract"]["not_before"]):
            errors.append("V4 result predates the not_before gate")
    except (TypeError, ValueError):
        errors.append("V4 result timestamp is invalid")
    v3_by_id = {row["availability_plan_id"]: row for row in v3["results"]}
    v4_by_id = {row["availability_plan_id"]: row for row in v4.get("results", [])}
    plan_ids = [row["availability_plan_id"] for row in plan]
    if len(v4.get("results", [])) != len(plan_ids) or list(v4_by_id) != plan_ids or set(v3_by_id) != set(v4_by_id):
        errors.append("V4 membership/order changed")
    prior_resolved = {key for key, row in v3_by_id.items() if row["error"] is None}
    prior_unresolved_order = [key for key in plan_ids if v3_by_id[key]["error"] is not None]
    prior_unresolved = set(prior_unresolved_order)
    for key in prior_resolved:
        if key in v4_by_id and canonical(v3_by_id[key]) != canonical(v4_by_id[key]):
            errors.append(f"Resolved V3 result changed: {key}")
    retried = [str(value) for value in v4.get("retried_availability_plan_ids", [])]
    if len(retried) != len(set(retried)) or not set(retried).issubset(prior_unresolved) or len(retried) != v4.get("network_request_count_this_attempt"):
        errors.append("V4 retried a resolved row, duplicated a retry, or changed the retry count")
    if retried != prior_unresolved_order[: len(retried)]:
        errors.append("V4 retry order changed")
    if not v4.get("stopped_on_http_429") and len(retried) != len(prior_unresolved_order):
        errors.append("V4 stopped early without an HTTP 429")
    available = unavailable = unresolved = 0
    for source in plan:
        key = source["availability_plan_id"]
        row = v4_by_id.get(key)
        if row is None:
            continue
        for field in ("availability_plan_id", "shortlist_id", "cohort", "candidate_host", "candidate_url"):
            if row.get(field) != source[field]:
                errors.append(f"V4 plan/result field mismatch: {key}:{field}")
        if row.get("query_timestamp") != source["target_timestamp"]:
            errors.append(f"V4 plan/result timestamp mismatch: {key}")
        if row.get("error") is not None:
            unresolved += 1
            if row.get("available") is not None:
                errors.append(f"Unresolved V4 row has availability: {key}")
        elif row.get("available") is True:
            available += 1
            if row.get("snapshot_http_status") != "200" or not valid_snapshot_url(str(row.get("snapshot_url") or ""), str(row.get("snapshot_timestamp") or "")):
                errors.append(f"Invalid available V4 row: {key}")
        elif row.get("available") is False:
            unavailable += 1
            if any(row.get(field) is not None for field in ("snapshot_timestamp", "snapshot_url", "snapshot_http_status")):
                errors.append(f"Unavailable V4 row retains evidence: {key}")
        else:
            errors.append(f"Resolved V4 row lacks availability: {key}")
    for field, value in (("available_snapshot_count", available), ("unavailable_snapshot_count", unavailable), ("unresolved_error_count", unresolved), ("requested_candidate_count", len(plan))):
        if v4.get(field) != value:
            errors.append(f"V4 aggregate mismatch: {field}")
    if v4.get("resolved_results_reused_from_v3") != len(prior_resolved) or v4.get("retry_candidate_count") != len(prior_unresolved):
        errors.append("V4 parent population aggregate changed")
    if v4.get("cumulative_network_request_count") != v3.get("cumulative_network_request_count") + v4.get("network_request_count_this_attempt", -1):
        errors.append("V4 cumulative request count mismatch")
    has_429 = any("HTTP 429" in str(row.get("error")) for row in v4.get("results", []))
    if bool(v4.get("stopped_on_http_429")) != has_429:
        errors.append("V4 HTTP 429 stop flag and evidence disagree")
    if v4.get("capture_plan_construction_ready") is not (unresolved == 0):
        errors.append("V4 capture-plan readiness does not match unresolved count")
    expected_report_status = "COMPLETE" if unresolved == 0 else "INCOMPLETE_ERRORS_PRESERVED"
    if v4.get("status") != expected_report_status:
        errors.append("V4 report status does not match unresolved count")
    if v4.get("safety_contract") != EXPECTED_SAFETY:
        errors.append("V4 safety contract changed")
    external_holdout_unresolved = sum(row.get("cohort") == "EXTERNAL_HOLDOUT" and row.get("error") is not None for row in v4.get("results", []))
    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_RESULT_INDEPENDENT_QA_V4",
        "status": pass_status(unresolved) if not errors else "FAIL",
        "inputs": {"release_sha256": sha256_file(release_path), "v3_sha256": sha256_file(v3_path), "v4_sha256": sha256_file(v4_path)},
        "checks": {
            "membership_and_order_preserved": not any("membership/order" in error for error in errors),
            "resolved_v3_results_preserved": not any("Resolved V3 result changed" in error for error in errors),
            "retried_only_prior_unresolved": set(retried).issubset(prior_unresolved),
            "not_before_gate_respected": not any("predates" in error for error in errors),
            "resolved_results": available + unavailable,
            "available_results": available,
            "unavailable_results": unavailable,
            "unresolved_results": unresolved,
            "external_holdout_unresolved": external_holdout_unresolved,
            "network_requests_v4": v4.get("network_request_count_this_attempt"),
            "cumulative_network_requests": v4.get("cumulative_network_request_count"),
            "stopped_on_http_429": v4.get("stopped_on_http_429"),
            "capture_plan_construction_ready": unresolved == 0 and not errors,
        },
        "errors": errors,
        "safety_contract": {"network_operations": 0, "candidate_domain_access_operations": 0, "archived_page_downloads": 0, "captures": 0, "labels": 0, "model": 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--v3", type=Path, required=True)
    parser.add_argument("--v4", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite V4 QA")
    result = verify(args.release, args.v3, args.v4)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
