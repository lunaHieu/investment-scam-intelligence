"""Independently verify the first adaptive B5 exact-70 availability retry."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.archive_retry_policy_v1 import MAX_NETWORK_ATTEMPTS_PER_ARTIFACT, POLICY_ID, decide
from scripts.verify_target_text_corpus_v1_ready_channel_wayback_availability_execution_amendment_v2 import (
    PASS_STATUS as AMENDMENT_PASS_STATUS,
    verify as verify_amendment,
)
from scripts.verify_target_text_corpus_v1_ready_channel_wayback_availability_result_v1 import (
    verify as verify_previous_result,
)
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


RELEASE_ID = "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_WAYBACK_AVAILABILITY_RETRY_RELEASE_V2"
QA_ID = "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_WAYBACK_AVAILABILITY_RETRY_RELEASE_QA_V2"
PASS_STATUS = "PASS_B5_EXACT_70_FIRST_ADAPTIVE_HTTP_429_RETRY_RELEASE"
PREVIOUS_QA_STATUS = "PASS_PARTIAL_ERRORS_PRESERVED_CAPTURE_PLAN_BLOCKED"
PRESERVED_HEADERS = ["Retry-After", "Date", "Server", "Content-Type", "X-Archive-Wayback-Runtime-Error"]


def _resolve(root: Path, item: dict[str, Any]) -> Path:
    path = Path(str(item.get("path", "")))
    return path if path.is_absolute() else root / path


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _check_file(root: Path, item: dict[str, Any], role: str, errors: list[str]) -> Path:
    path = _resolve(root, item)
    if not path.is_file() or sha256_file(path) != item.get("sha256"):
        errors.append(f"B5 retry input hash mismatch: {role}")
    return path


def verify(release_path: Path, *, require_output_absent: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    try:
        release = load_object(release_path)
    except Exception as error:
        return {"verification_id": QA_ID, "status": "FAIL", "errors": [f"Release load failed: {type(error).__name__}: {error}"]}
    root = release_path.resolve().parents[1]
    if release.get("release_id") != RELEASE_ID:
        errors.append("Unexpected B5 retry release identity")
    if release.get("status") != "FROZEN_EXACT_70_FIRST_ADAPTIVE_HTTP_429_RETRY":
        errors.append("Unexpected B5 retry release status")

    inputs = release.get("inputs", {})
    paths = {role: _check_file(root, item, role, errors) for role, item in inputs.items()}
    plan = _read_jsonl(paths["availability_plan"]) if paths.get("availability_plan", Path()).is_file() else []
    expected_ids = [f"TTCV1_B3_AVAIL_{index:03d}" for index in range(1, 71)]
    if len(plan) != 70 or inputs.get("availability_plan", {}).get("record_count") != 70:
        errors.append("B5 retry plan does not contain exactly 70 rows")
    if [row.get("availability_plan_id") for row in plan] != expected_ids:
        errors.append("B5 retry plan identity/order changed")
    development = sum(row.get("cohort") == "DEVELOPMENT" for row in plan)
    holdout = sum(row.get("cohort") == "EXTERNAL_HOLDOUT" for row in plan)
    identity = release.get("identity_contract", {})
    if (development, holdout) != (50, 20) or any(identity.get(key) != value for key, value in (
        ("expected_candidate_count", 70), ("expected_development_count", 50),
        ("expected_external_holdout_count", 20), ("resolved_rows_removed", 0),
        ("same_parent_release_rerun", False),
    )):
        errors.append("B5 retry identity/cohort contract changed")

    amendment_path = paths.get("execution_amendment", Path())
    if amendment_path.is_file():
        amendment_check = verify_amendment(amendment_path, require_output_absent=False)
        if amendment_check.get("status") != AMENDMENT_PASS_STATUS or amendment_check.get("errors"):
            errors.append("B5 V2 execution amendment no longer verifies")
        amendment = load_object(amendment_path)
    else:
        amendment = {}
    parent_path = paths.get("parent_release", Path())
    previous_report_path = paths.get("previous_report", Path())
    previous_qa_path = paths.get("previous_result_qa", Path())
    parent_qa_item = amendment.get("parent_release_qa", {})
    parent_qa_path = _resolve(root, parent_qa_item) if parent_qa_item else Path("__missing__")
    if parent_path.is_file() and parent_qa_path.is_file() and previous_report_path.is_file():
        previous_check = verify_previous_result(parent_path, parent_qa_path, previous_report_path)
        if previous_check.get("status") != PREVIOUS_QA_STATUS or previous_check.get("errors"):
            errors.append("Previous B5 result no longer independently verifies")
        if previous_qa_path.is_file() and load_object(previous_qa_path) != previous_check:
            errors.append("Stored previous B5 result QA differs from recomputation")

    try:
        previous = load_object(previous_report_path)
        results = previous["results"]
        first = results[0]
        headers = first.get("response_diagnostics", {}).get("response_headers", {})
        if previous.get("logical_attempt_count") != 1 or previous.get("network_request_count") != 1:
            errors.append("Previous B5 result is not the single-attempt trigger")
        if previous.get("unresolved_error_count") != 70 or previous.get("stopped_on_http_429") is not True:
            errors.append("Previous B5 result does not preserve the exact 70-row HTTP 429 stop")
        if first.get("availability_plan_id") != expected_ids[0] or first.get("snapshot_http_status") != "429":
            errors.append("Previous B5 triggering row is not the frozen first-row HTTP 429")
        if headers.get("Retry-After") is not None:
            errors.append("Previous B5 HTTP 429 unexpectedly contains Retry-After")
        if [row.get("availability_plan_id") for row in results] != expected_ids:
            errors.append("Previous B5 result identity/order changed")
        retry_after = headers.get("Retry-After")
    except (KeyError, IndexError, TypeError, OSError, json.JSONDecodeError) as error:
        retry_after = None
        errors.append(f"Previous B5 trigger evidence is invalid: {type(error).__name__}: {error}")

    policy = release.get("retry_policy", {})
    try:
        recomputed_policy = decide(
            failure_class="HTTP_429",
            observed_at=str(policy["observed_at"]),
            network_attempts=int(policy["network_attempts_for_triggering_row"]),
            consecutive_failures=int(policy["consecutive_failures"]),
            retry_after=retry_after,
        )
        if policy.get("policy_id") != POLICY_ID or policy.get("maximum_network_attempts_per_artifact_family") != MAX_NETWORK_ATTEMPTS_PER_ARTIFACT:
            errors.append("B5 adaptive retry policy identity/budget changed")
        for field in ("failure_class", "action", "not_before"):
            if policy.get(field) != recomputed_policy.get(field):
                errors.append(f"B5 adaptive retry decision mismatch: {field}")
        if datetime.fromisoformat(str(policy["not_before"])).tzinfo is None:
            errors.append("B5 retry not-before lacks timezone")
        if policy.get("universal_fixed_24h_retry_forbidden") is not True:
            errors.append("B5 retry reinstates the forbidden universal 24-hour gate")
    except (KeyError, TypeError, ValueError) as error:
        errors.append(f"B5 adaptive retry policy is invalid: {type(error).__name__}: {error}")

    contract = release.get("execution_contract", {})
    expected_contract = {
        "endpoint": "https://archive.org/wayback/available",
        "expected_candidate_count": 70,
        "expected_development_count": 50,
        "expected_external_holdout_count": 20,
        "minimum_delay_seconds": 60.0,
        "maximum_attempts_per_candidate": 1,
        "timeout_seconds": 30,
        "maximum_redirects": 3,
        "maximum_response_bytes": 2097152,
        "required_content_type_prefix": "application/json",
        "descriptive_user_agent_required": True,
        "partial_journal_reserved_before_network": True,
        "partial_journal_auto_resume_allowed": False,
        "stop_on_http_429": True,
        "stop_on_any_http_or_transport_error": True,
        "errors_are_preserved": True,
        "errors_are_not_interpreted_as_no_snapshot": True,
        "output_overwrite_allowed": False,
    }
    for field, expected in expected_contract.items():
        if contract.get(field) != expected:
            errors.append(f"B5 retry execution contract changed: {field}")
    if set(contract.get("allowed_network_hosts", [])) != {"archive.org", "web.archive.org"}:
        errors.append("B5 retry archive host allowlist changed")
    if contract.get("preserved_response_headers") != PRESERVED_HEADERS:
        errors.append("B5 retry preserved headers changed")

    decision = release.get("decision", {})
    if decision.get("retry_allowed_at_or_after_not_before") is not True or decision.get("parent_release_rerun_allowed") is not False:
        errors.append("B5 retry decision does not isolate the new release")
    for gate in ("candidate_live_domain_access_allowed", "archived_page_download_allowed", "artifact_capture_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "model_scoring_allowed", "training_allowed"):
        if decision.get(gate) is not False:
            errors.append(f"B5 retry forbidden gate opened: {gate}")

    output = Path(str(release.get("planned_output", {}).get("path", "")))
    partial = output.with_suffix(output.suffix + str(release.get("planned_output", {}).get("partial_journal_suffix", ".partial")))
    if require_output_absent and (output.exists() or partial.exists()):
        errors.append("B5 retry final or partial output already exists")
    return {
        "verification_id": QA_ID,
        "status": PASS_STATUS if not errors else "FAIL",
        "release": {"path": str(release_path.resolve()), "sha256": sha256_file(release_path)},
        "checks": {
            "plan_rows": len(plan), "development_rows": development, "external_holdout_rows": holdout,
            "previous_attempts": 1, "previous_http_429_without_retry_after": retry_after is None,
            "adaptive_policy_id": policy.get("policy_id"), "not_before": policy.get("not_before"),
            "output_absent": not output.exists() and not partial.exists(), "network_operations": 0,
        },
        "decision": {"release_prepared": not errors, "retry_allowed_at_or_after_not_before": not errors, "capture_allowed": False, "training_allowed": False},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "candidate_domain_access_operations": 0, "archived_page_downloads": 0, "captures": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--allow-existing-output", action="store_true")
    args = parser.parse_args()
    result = verify(args.release, require_output_absent=not args.allow_existing_output)
    if args.output and result["status"] != "FAIL":
        partial = args.output.with_suffix(args.output.suffix + ".partial")
        if args.output.exists() or partial.exists():
            raise FileExistsError("Refusing to overwrite B5 retry release QA")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
