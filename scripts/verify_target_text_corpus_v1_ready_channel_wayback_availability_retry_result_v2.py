"""Independently verify the adaptive B5 exact-70 availability retry result."""

from __future__ import annotations

import argparse
import json
import re
import urllib.parse
from pathlib import Path
from typing import Any

from scripts.execute_target_text_corpus_v1_ready_channel_wayback_availability_v1 import EXECUTOR as RUNNER_EXECUTOR
from scripts.execute_target_text_corpus_v1_ready_channel_wayback_availability_retry_v2 import EXECUTOR as WRAPPER_EXECUTOR
from scripts.verify_target_text_corpus_v1_ready_channel_wayback_availability_retry_release_v2 import (
    PASS_STATUS as RELEASE_PASS_STATUS,
    verify as verify_release,
)
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


QA_ID = "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_WAYBACK_AVAILABILITY_RETRY_RESULT_QA_V2"
COMPLETE_STATUS = "PASS_COMPLETE_EXACT_70_RETRY_CAPTURE_PLAN_MAY_BE_PREPARED"
PARTIAL_STATUS = "PASS_PARTIAL_RETRY_ERRORS_PRESERVED_CAPTURE_PLAN_BLOCKED"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _valid_snapshot_url(value: str, timestamp: str) -> bool:
    parsed = urllib.parse.urlsplit(value)
    return parsed.scheme == "https" and (parsed.hostname or "").casefold() == "web.archive.org" and bool(re.match(rf"^/web/{re.escape(timestamp)}/https?://", parsed.path))


def verify(release_path: Path, release_qa_path: Path, report_path: Path, *, require_frozen_output_path: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    try:
        release = load_object(release_path)
        release_qa = load_object(release_qa_path)
        report = load_object(report_path)
    except Exception as error:
        return {"verification_id": QA_ID, "status": "FAIL", "errors": [f"Input loading failed: {type(error).__name__}: {error}"]}

    release_check = verify_release(release_path, require_output_absent=False)
    if release_check.get("status") != RELEASE_PASS_STATUS or release_check.get("errors"):
        errors.append("Frozen B5 retry release no longer verifies")
    if release_qa.get("status") != RELEASE_PASS_STATUS or release_qa.get("errors") != [] or release_qa.get("release", {}).get("sha256") != sha256_file(release_path):
        errors.append("Frozen B5 retry release QA is not authoritative PASS")
    if require_frozen_output_path and Path(str(release["planned_output"]["path"])) != report_path:
        errors.append("B5 retry report is not the frozen output path")
    partial = report_path.with_suffix(report_path.suffix + str(release["planned_output"]["partial_journal_suffix"]))
    if partial.exists():
        errors.append("B5 retry final report still has a partial journal")

    plan_path = Path(str(release["inputs"]["availability_plan"]["path"]))
    plan = _read_jsonl(plan_path)
    if report.get("report_id") != release["planned_output"]["report_id"] or report.get("executor") != RUNNER_EXECUTOR:
        errors.append("B5 retry result identity or immutable runner changed")
    if report.get("release_sha256") != sha256_file(release_path) or report.get("release_qa_sha256") != sha256_file(release_qa_path) or report.get("plan_sha256") != release["inputs"]["availability_plan"]["sha256"]:
        errors.append("B5 retry result input binding changed")

    coordination = report.get("coordination_evidence", {})
    expected_coordination = {
        "coordination_policy": release["retry_policy"]["policy_id"],
        "failure_class": release["retry_policy"]["failure_class"],
        "consecutive_failures_before_release": release["retry_policy"]["consecutive_failures"],
        "network_attempts_before_release": release["retry_policy"]["network_attempts_for_triggering_row"],
        "retry_after_header": release["retry_policy"]["retry_after_header"],
        "not_before": release["retry_policy"]["not_before"],
        "universal_fixed_24h_retry_forbidden": True,
        "authoritative_wrapper": WRAPPER_EXECUTOR,
        "immutable_runner": "scripts.execute_target_text_corpus_v1_ready_channel_wayback_availability_v1.run_plan",
    }
    for field, expected in expected_coordination.items():
        if coordination.get(field) != expected:
            errors.append(f"B5 retry coordination evidence changed: {field}")
    for role in ("previous_report", "previous_result_qa"):
        path = Path(str(coordination.get(f"{role}_path", "")))
        if not path.is_file() or sha256_file(path) != coordination.get(f"{role}_sha256") or coordination.get(f"{role}_sha256") != release["inputs"][role]["sha256"]:
            errors.append(f"B5 retry coordination evidence hash changed: {role}")

    results = report.get("results", [])
    if len(plan) != 70 or not isinstance(results, list) or len(results) != 70:
        errors.append("B5 retry result coverage is not exactly 70")
        results = results if isinstance(results, list) else []
    unresolved = available = unavailable = queried = 0
    for source, result in zip(plan, results):
        for field in ("availability_plan_id", "candidate_id", "cohort", "channel_id", "channel_target_stratum", "candidate_host", "candidate_url", "target_timestamp"):
            if result.get(field) != source.get(field):
                errors.append(f"B5 retry plan/result mismatch: {source.get('availability_plan_id')}:{field}")
        if result.get("queried") is True:
            queried += 1
        if result.get("error") is not None:
            unresolved += 1
            if result.get("available") is not None:
                errors.append(f"B5 retry unresolved row has availability: {source.get('availability_plan_id')}")
        elif result.get("available") is True:
            available += 1
            timestamp = str(result.get("snapshot_timestamp") or "")
            if result.get("snapshot_http_status") != "200" or not re.fullmatch(r"\d{14}", timestamp) or not _valid_snapshot_url(str(result.get("snapshot_url") or ""), timestamp):
                errors.append(f"B5 retry available snapshot evidence is invalid: {source.get('availability_plan_id')}")
        elif result.get("available") is False:
            unavailable += 1
            if result.get("snapshot_timestamp") is not None or result.get("snapshot_url") is not None:
                errors.append(f"B5 retry unavailable row retains snapshot evidence: {source.get('availability_plan_id')}")
        else:
            errors.append(f"B5 retry resolved row lacks availability: {source.get('availability_plan_id')}")

    logical_attempts = report.get("logical_attempt_count")
    network_requests = report.get("network_request_count")
    if logical_attempts != queried or not isinstance(network_requests, int) or network_requests < queried or network_requests > queried * (1 + int(release["execution_contract"]["maximum_redirects"])):
        errors.append("B5 retry logical/network request accounting is invalid")
    for field, value in (("requested_candidate_count", 70), ("available_snapshot_count", available), ("unavailable_snapshot_count", unavailable), ("unresolved_error_count", unresolved)):
        if report.get(field) != value:
            errors.append(f"B5 retry aggregate mismatch: {field}")
    stopped = report.get("stopped_fail_closed") is True
    if stopped != (unresolved > 0):
        errors.append("B5 retry fail-closed stop and unresolved state disagree")
    if report.get("stopped_on_http_429") is True and not any(result.get("snapshot_http_status") == "429" for result in results):
        errors.append("B5 retry HTTP 429 stop lacks row evidence")
    complete = unresolved == 0
    if report.get("status") != ("COMPLETE" if complete else "INCOMPLETE_ERRORS_PRESERVED"):
        errors.append("B5 retry report status does not match unresolved count")
    if report.get("capture_plan_construction_ready") is not complete:
        errors.append("B5 retry capture-plan readiness does not match completeness")
    expected_safety = {"candidate_live_domain_access_operations": 0, "only_archive_availability_hosts_accessed": True, "archived_page_download_operations": 0, "artifact_captures": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False}
    if report.get("safety_contract") != expected_safety:
        errors.append("B5 retry result safety contract changed")

    status = "FAIL" if errors else (COMPLETE_STATUS if complete else PARTIAL_STATUS)
    return {
        "verification_id": QA_ID,
        "status": status,
        "inputs": {"release_sha256": sha256_file(release_path), "release_qa_sha256": sha256_file(release_qa_path), "plan_sha256": sha256_file(plan_path), "report_sha256": sha256_file(report_path)},
        "checks": {"plan_rows": len(plan), "result_rows": len(results), "logical_attempts": logical_attempts, "network_requests": network_requests, "available_results": available, "unavailable_results": unavailable, "unresolved_results": unresolved, "stopped_on_http_429": report.get("stopped_on_http_429"), "capture_plan_construction_ready": complete and not errors, "coordination_evidence_hashes_valid": not any("coordination evidence" in error for error in errors)},
        "decision": {"availability_result_complete": complete and not errors, "capture_plan_preparation_allowed": complete and not errors, "capture_allowed": False, "labeling_allowed": False, "training_allowed": False},
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
        raise FileExistsError("Refusing to overwrite B5 retry result QA")
    result = verify(args.release, args.release_qa, args.report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
