"""Independently verify a future SEC/IAPD Wayback availability V7 result."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.verify_sec_edgar_iapd_wayback_availability_result_v1 import read_jsonl, valid_snapshot_url
from scripts.verify_sec_edgar_iapd_wayback_availability_result_v4 import EXPECTED_SAFETY, canonical, parse_time, pass_status
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def verify(release_path: Path, v6_path: Path, v7_path: Path) -> dict[str, Any]:
    release = load_object(release_path)
    parent = load_object(v6_path)
    current = load_object(v7_path)
    plan = read_jsonl(Path(release["inputs"]["availability_plan"]["path"]))
    errors: list[str] = []
    if current.get("report_id") != "ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_AVAILABILITY_REPORT_V7":
        errors.append("Unexpected V7 report identity")
    if current.get("executor") != "scripts.retry_sec_edgar_iapd_wayback_availability_v7":
        errors.append("Unexpected V7 executor identity")
    if current.get("release_sha256") != sha256_file(release_path):
        errors.append("V7 release hash mismatch")
    if current.get("parent_report_sha256") != sha256_file(v6_path):
        errors.append("V7 parent hash mismatch")
    if current.get("plan_sha256") != sha256_file(Path(release["inputs"]["availability_plan"]["path"])):
        errors.append("V7 plan hash mismatch")
    try:
        if parse_time(str(current.get("created_at"))) < parse_time(release["cooldown_contract"]["not_before"]):
            errors.append("V7 result predates the not_before gate")
    except (TypeError, ValueError):
        errors.append("V7 result timestamp is invalid")

    parent_by_id = {row["availability_plan_id"]: row for row in parent["results"]}
    current_rows = current.get("results", [])
    current_by_id = {row["availability_plan_id"]: row for row in current_rows}
    plan_ids = [row["availability_plan_id"] for row in plan]
    if len(current_rows) != len(plan_ids) or list(current_by_id) != plan_ids or set(parent_by_id) != set(current_by_id):
        errors.append("V7 membership/order changed")

    prior_resolved = {key for key, row in parent_by_id.items() if row.get("error") is None}
    prior_unresolved_order = [key for key in plan_ids if parent_by_id[key].get("error") is not None]
    prior_unresolved = set(prior_unresolved_order)
    if prior_unresolved_order != release["prior_outcome_contract"].get("ordered_unresolved_availability_plan_ids"):
        errors.append("V7 parent unresolved identity/order differs from the frozen release")
    observed_unresolved_cohorts = {
        cohort: sum(
            parent_by_id[key].get("cohort") == cohort for key in prior_unresolved_order
        )
        for cohort in ("DEVELOPMENT", "EXTERNAL_HOLDOUT")
    }
    if observed_unresolved_cohorts != release["prior_outcome_contract"].get("unresolved_cohort_counts"):
        errors.append("V7 parent unresolved cohort composition differs from the frozen release")
    for key in prior_resolved:
        if key in current_by_id and canonical(parent_by_id[key]) != canonical(current_by_id[key]):
            errors.append(f"Resolved V6 result changed: {key}")
    retried = [str(value) for value in current.get("retried_availability_plan_ids", [])]
    logical_attempts = current.get("logical_retry_attempt_count")
    network_requests = current.get("network_request_count_this_attempt")
    if len(retried) != len(set(retried)) or not set(retried).issubset(prior_unresolved):
        errors.append("V7 retried a resolved row or duplicated a logical retry")
    if logical_attempts != len(retried):
        errors.append("V7 logical retry count changed")
    max_redirects = int(release["retry_contract"]["maximum_redirects"])
    if (
        not isinstance(network_requests, int)
        or network_requests < len(retried)
        or network_requests > len(retried) * (1 + max_redirects)
    ):
        errors.append("V7 HTTP request count is outside the logical-attempt redirect bound")
    if retried != prior_unresolved_order[: len(retried)]:
        errors.append("V7 retry order changed")
    if not current.get("stopped_on_http_429") and len(retried) != len(prior_unresolved_order):
        errors.append("V7 stopped early without an HTTP 429")

    available = unavailable = unresolved = 0
    for source in plan:
        key = source["availability_plan_id"]
        row = current_by_id.get(key)
        if row is None:
            continue
        for field in ("availability_plan_id", "shortlist_id", "cohort", "candidate_host", "candidate_url"):
            if row.get(field) != source[field]:
                errors.append(f"V7 plan/result field mismatch: {key}:{field}")
        if row.get("query_timestamp") != source["target_timestamp"]:
            errors.append(f"V7 plan/result timestamp mismatch: {key}")
        if row.get("error") is not None:
            unresolved += 1
            if row.get("available") is not None:
                errors.append(f"Unresolved V7 row has availability: {key}")
        elif row.get("available") is True:
            available += 1
            if row.get("snapshot_http_status") != "200" or not valid_snapshot_url(
                str(row.get("snapshot_url") or ""), str(row.get("snapshot_timestamp") or "")
            ):
                errors.append(f"Invalid available V7 row: {key}")
        elif row.get("available") is False:
            unavailable += 1
            if any(row.get(field) is not None for field in ("snapshot_timestamp", "snapshot_url", "snapshot_http_status")):
                errors.append(f"Unavailable V7 row retains evidence: {key}")
        else:
            errors.append(f"Resolved V7 row lacks availability: {key}")

    for field, value in (
        ("available_snapshot_count", available),
        ("unavailable_snapshot_count", unavailable),
        ("unresolved_error_count", unresolved),
        ("requested_candidate_count", len(plan)),
    ):
        if current.get(field) != value:
            errors.append(f"V7 aggregate mismatch: {field}")
    if current.get("resolved_results_reused_from_v6") != len(prior_resolved):
        errors.append("V7 resolved-parent population changed")
    if current.get("retry_candidate_count") != len(prior_unresolved):
        errors.append("V7 retry population aggregate changed")
    if current.get("cumulative_network_request_count") != parent.get("cumulative_network_request_count") + current.get(
        "network_request_count_this_attempt", -1
    ):
        errors.append("V7 cumulative request count mismatch")
    has_429 = any("429" in str(row.get("error")) for row in current_rows)
    if bool(current.get("stopped_on_http_429")) != has_429:
        errors.append("V7 HTTP 429 stop flag and evidence disagree")
    if current.get("capture_plan_construction_ready") is not (unresolved == 0):
        errors.append("V7 capture-plan readiness does not match unresolved count")
    if current.get("status") != ("COMPLETE" if unresolved == 0 else "INCOMPLETE_ERRORS_PRESERVED"):
        errors.append("V7 report status does not match unresolved count")
    if current.get("safety_contract") != EXPECTED_SAFETY:
        errors.append("V7 safety contract changed")

    external_holdout_unresolved = sum(
        row.get("cohort") == "EXTERNAL_HOLDOUT" and row.get("error") is not None for row in current_rows
    )
    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_RESULT_INDEPENDENT_QA_V7",
        "status": pass_status(unresolved) if not errors else "FAIL",
        "inputs": {
            "release_sha256": sha256_file(release_path),
            "v6_sha256": sha256_file(v6_path),
            "v7_sha256": sha256_file(v7_path),
        },
        "checks": {
            "membership_and_order_preserved": not any("membership/order" in error for error in errors),
            "resolved_v6_results_preserved": not any("Resolved V6 result changed" in error for error in errors),
            "retried_only_prior_unresolved": set(retried).issubset(prior_unresolved),
            "not_before_gate_respected": not any("predates" in error for error in errors),
            "resolved_results": available + unavailable,
            "available_results": available,
            "unavailable_results": unavailable,
            "unresolved_results": unresolved,
            "external_holdout_unresolved": external_holdout_unresolved,
            "logical_retry_attempts_v7": logical_attempts,
            "network_requests_v7": network_requests,
            "cumulative_network_requests": current.get("cumulative_network_request_count"),
            "stopped_on_http_429": current.get("stopped_on_http_429"),
            "capture_plan_construction_ready": unresolved == 0 and not errors,
        },
        "errors": errors,
        "safety_contract": {
            "network_operations": 0,
            "candidate_domain_access_operations": 0,
            "archived_page_downloads": 0,
            "captures": 0,
            "labels": 0,
            "model": 0,
            "training_allowed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--v6", type=Path, required=True)
    parser.add_argument("--v7", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    if args.output.exists() or partial.exists():
        raise FileExistsError("Refusing to overwrite V7 QA")
    result = verify(args.release, args.v6, args.v7)
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
