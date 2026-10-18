"""Independently verify the frozen SEC/IAPD Wayback retry V7 release."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.retry_sec_edgar_iapd_wayback_availability_v4 import read_jsonl
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def verify(release_path: Path) -> dict[str, Any]:
    release = load_object(release_path)
    errors: list[str] = []
    if release.get("release_id") != "ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_RETRY_RELEASE_V7":
        errors.append("Unexpected V7 retry release identity")
    root = release_path.resolve().parents[1]
    for item in release.get("basis", []):
        path = root / item["path"]
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            errors.append(f"Basis hash mismatch: {item['path']}")
    for role, item in release.get("inputs", {}).items():
        path = Path(item["path"])
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            errors.append(f"Input hash mismatch: {role}")

    prior = load_object(Path(release["inputs"]["partial_report_v6"]["path"]))
    qa = load_object(Path(release["inputs"]["independent_qa_v6"]["path"]))
    plan = read_jsonl(Path(release["inputs"]["availability_plan"]["path"]))
    if qa.get("status") != "PASS_PARTIAL_ERRORS_PRESERVED_CAPTURE_PLAN_BLOCKED":
        errors.append("V6 independent QA status changed")
    if [row["availability_plan_id"] for row in plan] != [row["availability_plan_id"] for row in prior["results"]]:
        errors.append("Plan/V6 membership or order changed")

    resolved = sum(row.get("error") is None for row in prior["results"])
    unresolved = sum(row.get("error") is not None for row in prior["results"])
    observed = {
        "requested_candidate_count": len(prior["results"]),
        "cumulative_network_request_count": prior["cumulative_network_request_count"],
        "resolved_result_count": resolved,
        "available_snapshot_count": sum(row.get("available") is True for row in prior["results"]),
        "unavailable_snapshot_count": sum(row.get("available") is False for row in prior["results"]),
        "unresolved_error_count": unresolved,
        "stopped_on_http_429": prior["stopped_on_http_429"],
    }
    for key, value in observed.items():
        if release["prior_outcome_contract"].get(key) != value:
            errors.append(f"Prior outcome mismatch: {key}")
    if release["prior_outcome_contract"].get("resolved_results_must_remain_byte_equivalent") is not True:
        errors.append("Resolved-row preservation contract is not explicit")
    if release["prior_outcome_contract"].get("only_error_rows_may_be_retried") is not True:
        errors.append("Unresolved-only retry contract is not explicit")
    unresolved_ids = [
        str(row["availability_plan_id"]) for row in prior["results"] if row.get("error") is not None
    ]
    if unresolved_ids != release["prior_outcome_contract"].get("ordered_unresolved_availability_plan_ids"):
        errors.append("V7 ordered unresolved identity set changed")
    unresolved_cohorts = {
        cohort: sum(
            row.get("error") is not None and row.get("cohort") == cohort for row in prior["results"]
        )
        for cohort in ("DEVELOPMENT", "EXTERNAL_HOLDOUT")
    }
    if unresolved_cohorts != release["prior_outcome_contract"].get("unresolved_cohort_counts"):
        errors.append("V7 unresolved cohort composition changed")

    cooldown = release["cooldown_contract"]
    parent_created = datetime.fromisoformat(prior["created_at"])
    release_created = datetime.fromisoformat(release["created_at"])
    declared_parent = datetime.fromisoformat(cooldown["prior_attempt_created_at"])
    not_before = datetime.fromisoformat(cooldown["not_before"])
    cooldown_seconds = (not_before - parent_created).total_seconds()
    if parent_created != declared_parent:
        errors.append("V7 cooldown is not bound to the actual V6 created_at")
    if cooldown_seconds < 86400 or cooldown["minimum_cooldown_seconds"] < 86400:
        errors.append("V7 cooldown is shorter than 24 hours")
    if cooldown_seconds != cooldown["minimum_cooldown_seconds"]:
        errors.append("V7 not_before does not equal parent created_at plus cooldown")
    if release_created < parent_created or release_created >= not_before:
        errors.append("V7 release created_at is outside the offline preparation window")

    contract = release["retry_contract"]
    if contract["maximum_retry_candidate_count"] != unresolved or unresolved != 8:
        errors.append("V7 retry population changed")
    if float(contract["minimum_delay_seconds"]) < 60.0:
        errors.append("V7 minimum pacing is below 60 seconds")
    if float(contract["request_rate_per_second_maximum"]) > (1.0 / 60.0) + 1e-9:
        errors.append("V7 request-rate ceiling is too high")
    if contract["maximum_attempts_per_candidate"] != 1:
        errors.append("V7 attempt budget changed")
    if contract.get("timeout_seconds") != 30:
        errors.append("V7 timeout changed")
    if contract.get("maximum_redirects") != 3:
        errors.append("V7 maximum redirects changed")
    if contract.get("maximum_response_bytes") != 2097152:
        errors.append("V7 response-size bound changed")
    if contract["endpoint"] != "https://archive.org/wayback/available":
        errors.append("V7 endpoint changed")
    if set(contract["allowed_network_hosts"]) != {"archive.org", "web.archive.org"}:
        errors.append("V7 allowlist changed")
    if contract.get("stop_on_http_429") is not True or contract.get("output_overwrite_allowed") is not False:
        errors.append("V7 stop/no-overwrite contract changed")
    expected_output = Path(release["inputs"]["partial_report_v6"]["path"]).parent / "availability_report_v7.json"
    if Path(release["planned_output"].get("path", "")) != expected_output:
        errors.append("V7 planned output path changed")
    if release["planned_output"].get("report_id") != "ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_AVAILABILITY_REPORT_V7":
        errors.append("V7 planned report identity changed")

    decision = release["decision"]
    if decision.get("network_execution_allowed_now") is not False:
        errors.append("V7 preparation authorizes immediate execution")
    for gate in (
        "candidate_live_domain_access_allowed",
        "archived_page_download_allowed",
        "artifact_capture_allowed",
        "labeling_allowed",
        "validation_or_test_opening_allowed",
        "training_allowed",
    ):
        if decision.get(gate) is not False:
            errors.append(f"Forbidden gate opened: {gate}")

    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_RETRY_RELEASE_INDEPENDENT_QA_V7",
        "status": "PASS_FROZEN_NOT_BEFORE_24H_UNRESOLVED_ONLY_CRASH_SAFE_PACING_PRESERVED" if not errors else "FAIL",
        "inputs": {
            "release_sha256": sha256_file(release_path),
            "partial_report_v6_sha256": sha256_file(Path(release["inputs"]["partial_report_v6"]["path"])),
            "independent_qa_v6_sha256": sha256_file(Path(release["inputs"]["independent_qa_v6"]["path"])),
        },
        "checks": {
            "plan_rows": len(plan),
            "resolved_rows_preserved": resolved,
            "retry_rows": unresolved,
            "ordered_unresolved_availability_plan_ids": unresolved_ids,
            "unresolved_cohort_counts": unresolved_cohorts,
            "minimum_cooldown_seconds": cooldown_seconds,
            "not_before": cooldown["not_before"],
            "minimum_delay_seconds": contract["minimum_delay_seconds"],
            "maximum_attempts_per_candidate": contract["maximum_attempts_per_candidate"],
            "timeout_seconds": contract["timeout_seconds"],
            "maximum_redirects": contract["maximum_redirects"],
            "maximum_response_bytes": contract["maximum_response_bytes"],
            "network_execution_allowed_at_release_time": False,
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
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.release)
    if args.output:
        partial = args.output.with_suffix(args.output.suffix + ".partial")
        if args.output.exists() or partial.exists():
            raise FileExistsError("Refusing to overwrite V7 release QA")
        partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
