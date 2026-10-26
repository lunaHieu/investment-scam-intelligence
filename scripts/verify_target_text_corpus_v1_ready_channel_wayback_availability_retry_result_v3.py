"""Independently verify the second adaptive B5 retry result."""

from __future__ import annotations

import argparse
import json
import re
import urllib.parse
from pathlib import Path
from typing import Any

from scripts.execute_target_text_corpus_v1_ready_channel_wayback_availability_v1 import EXECUTOR as RUNNER_EXECUTOR
from scripts.execute_target_text_corpus_v1_ready_channel_wayback_availability_retry_v3 import EXECUTOR as WRAPPER_EXECUTOR
from scripts.verify_target_text_corpus_v1_ready_channel_wayback_availability_retry_release_v3 import PASS_STATUS as RELEASE_PASS_STATUS, verify as verify_release
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


QA_ID = "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_WAYBACK_AVAILABILITY_RETRY_RESULT_QA_V3"
COMPLETE_STATUS = "PASS_COMPLETE_EXACT_70_V3_RETRY_CAPTURE_PLAN_MAY_BE_PREPARED"
PARTIAL_STATUS = "PASS_PARTIAL_V3_RETRY_ERRORS_PRESERVED_TRIGGER_ROW_BUDGET_EXHAUSTED"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _valid_snapshot_url(value: str, timestamp: str) -> bool:
    parsed = urllib.parse.urlsplit(value)
    return parsed.scheme == "https" and (parsed.hostname or "").casefold() == "web.archive.org" and bool(re.match(rf"^/web/{re.escape(timestamp)}/https?://", parsed.path))


def verify(release_path: Path, release_qa_path: Path, report_path: Path, *, require_frozen_output_path: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    try:
        release, release_qa, report = load_object(release_path), load_object(release_qa_path), load_object(report_path)
    except Exception as error:
        return {"verification_id": QA_ID, "status": "FAIL", "errors": [f"Input loading failed: {type(error).__name__}: {error}"]}
    release_check = verify_release(release_path, require_output_absent=False)
    if release_check.get("status") != RELEASE_PASS_STATUS or release_check.get("errors"):
        errors.append("Frozen B5 V3 retry release no longer verifies")
    if release_qa.get("status") != RELEASE_PASS_STATUS or release_qa.get("errors") != [] or release_qa.get("release", {}).get("sha256") != sha256_file(release_path):
        errors.append("Frozen B5 V3 retry release QA is not authoritative PASS")
    if require_frozen_output_path and Path(str(release["planned_output"]["path"])) != report_path:
        errors.append("B5 V3 retry report is not the frozen output path")
    partial = report_path.with_suffix(report_path.suffix + str(release["planned_output"]["partial_journal_suffix"]))
    if partial.exists():
        errors.append("B5 V3 retry final report still has a partial journal")

    plan_path = Path(str(release["inputs"]["availability_plan"]["path"]))
    plan = _read_jsonl(plan_path)
    if report.get("report_id") != release["planned_output"]["report_id"] or report.get("executor") != RUNNER_EXECUTOR:
        errors.append("B5 V3 retry result identity or immutable runner changed")
    if report.get("release_sha256") != sha256_file(release_path) or report.get("release_qa_sha256") != sha256_file(release_qa_path) or report.get("plan_sha256") != release["inputs"]["availability_plan"]["sha256"]:
        errors.append("B5 V3 retry result input binding changed")
    coordination = report.get("coordination_evidence", {})
    expected = {"coordination_policy": release["retry_policy"]["policy_id"], "failure_class": "HTTP_429", "consecutive_failures_before_release": 2, "network_attempts_before_release": 2, "retry_after_header": None, "not_before": release["retry_policy"]["not_before"], "triggering_row_final_attempt": True, "universal_fixed_24h_retry_forbidden": True, "authoritative_wrapper": WRAPPER_EXECUTOR, "immutable_runner": "scripts.execute_target_text_corpus_v1_ready_channel_wayback_availability_v1.run_plan"}
    for field, value in expected.items():
        if coordination.get(field) != value:
            errors.append(f"B5 V3 retry coordination evidence changed: {field}")
    for role in ("previous_report", "previous_result_qa"):
        path = Path(str(coordination.get(f"{role}_path", "")))
        if not path.is_file() or sha256_file(path) != coordination.get(f"{role}_sha256") or coordination.get(f"{role}_sha256") != release["inputs"][role]["sha256"]:
            errors.append(f"B5 V3 retry coordination evidence hash changed: {role}")

    results = report.get("results", [])
    if len(plan) != 70 or not isinstance(results, list) or len(results) != 70:
        errors.append("B5 V3 retry result coverage is not exactly 70")
        results = results if isinstance(results, list) else []
    unresolved = available = unavailable = queried = 0
    for source, result in zip(plan, results):
        for field in ("availability_plan_id", "candidate_id", "cohort", "channel_id", "channel_target_stratum", "candidate_host", "candidate_url", "target_timestamp"):
            if result.get(field) != source.get(field):
                errors.append(f"B5 V3 plan/result mismatch: {source.get('availability_plan_id')}:{field}")
        queried += result.get("queried") is True
        if result.get("error") is not None:
            unresolved += 1
            if result.get("available") is not None:
                errors.append(f"B5 V3 unresolved row has availability: {source.get('availability_plan_id')}")
        elif result.get("available") is True:
            available += 1
            timestamp = str(result.get("snapshot_timestamp") or "")
            if result.get("snapshot_http_status") != "200" or not re.fullmatch(r"\d{14}", timestamp) or not _valid_snapshot_url(str(result.get("snapshot_url") or ""), timestamp):
                errors.append(f"B5 V3 available snapshot evidence is invalid: {source.get('availability_plan_id')}")
        elif result.get("available") is False:
            unavailable += 1
            if result.get("snapshot_timestamp") is not None or result.get("snapshot_url") is not None:
                errors.append(f"B5 V3 unavailable row retains snapshot evidence: {source.get('availability_plan_id')}")
        else:
            errors.append(f"B5 V3 resolved row lacks availability: {source.get('availability_plan_id')}")
    logical, network = report.get("logical_attempt_count"), report.get("network_request_count")
    if logical != queried or not isinstance(network, int) or network < queried or network > queried * (1 + int(release["execution_contract"]["maximum_redirects"])):
        errors.append("B5 V3 logical/network request accounting is invalid")
    for field, value in (("requested_candidate_count", 70), ("available_snapshot_count", available), ("unavailable_snapshot_count", unavailable), ("unresolved_error_count", unresolved)):
        if report.get(field) != value:
            errors.append(f"B5 V3 aggregate mismatch: {field}")
    complete = unresolved == 0
    if (report.get("stopped_fail_closed") is True) != (unresolved > 0):
        errors.append("B5 V3 fail-closed stop and unresolved state disagree")
    if report.get("stopped_on_http_429") is True and not any(row.get("snapshot_http_status") == "429" for row in results):
        errors.append("B5 V3 HTTP 429 stop lacks row evidence")
    if report.get("status") != ("COMPLETE" if complete else "INCOMPLETE_ERRORS_PRESERVED") or report.get("capture_plan_construction_ready") is not complete:
        errors.append("B5 V3 status/readiness does not match completeness")
    expected_safety = {"candidate_live_domain_access_operations": 0, "only_archive_availability_hosts_accessed": True, "archived_page_download_operations": 0, "artifact_captures": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False}
    if report.get("safety_contract") != expected_safety:
        errors.append("B5 V3 result safety contract changed")
    status = "FAIL" if errors else (COMPLETE_STATUS if complete else PARTIAL_STATUS)
    return {
        "verification_id": QA_ID, "status": status,
        "inputs": {"release_sha256": sha256_file(release_path), "release_qa_sha256": sha256_file(release_qa_path), "plan_sha256": sha256_file(plan_path), "report_sha256": sha256_file(report_path)},
        "checks": {"plan_rows": len(plan), "result_rows": len(results), "logical_attempts": logical, "network_requests": network, "available_results": available, "unavailable_results": unavailable, "unresolved_results": unresolved, "stopped_on_http_429": report.get("stopped_on_http_429"), "capture_plan_construction_ready": complete and not errors, "triggering_row_retry_budget_exhausted_if_http_429": not complete and report.get("stopped_on_http_429") is True and not errors},
        "decision": {"availability_result_complete": complete and not errors, "capture_plan_preparation_allowed": complete and not errors, "another_identical_trigger_row_retry_allowed": False if not complete else None, "capture_allowed": False, "labeling_allowed": False, "training_allowed": False},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "candidate_domain_access_operations": 0, "archived_page_downloads": 0, "captures": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False},
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
        raise FileExistsError("Refusing to overwrite B5 V3 retry result QA")
    result = verify(args.release, args.release_qa, args.report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
