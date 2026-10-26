"""Independently verify the second adaptive B5 retry (third trigger-row attempt)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.archive_retry_policy_v1 import MAX_NETWORK_ATTEMPTS_PER_ARTIFACT, POLICY_ID, decide
from scripts.verify_target_text_corpus_v1_ready_channel_wayback_availability_retry_release_v2 import (
    PASS_STATUS as V2_RELEASE_PASS_STATUS,
    PRESERVED_HEADERS,
    verify as verify_v2_release,
)
from scripts.verify_target_text_corpus_v1_ready_channel_wayback_availability_retry_result_v2 import (
    PARTIAL_STATUS as V2_RESULT_PARTIAL_STATUS,
    verify as verify_v2_result,
)
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


RELEASE_ID = "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_WAYBACK_AVAILABILITY_RETRY_RELEASE_V3"
QA_ID = "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_WAYBACK_AVAILABILITY_RETRY_RELEASE_QA_V3"
PASS_STATUS = "PASS_B5_EXACT_70_SECOND_ADAPTIVE_HTTP_429_RETRY_FINAL_TRIGGER_ROW_ATTEMPT"


def _resolve(root: Path, item: dict[str, Any]) -> Path:
    path = Path(str(item.get("path", "")))
    return path if path.is_absolute() else root / path


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _check_file(root: Path, item: dict[str, Any], role: str, errors: list[str]) -> Path:
    path = _resolve(root, item)
    if not path.is_file() or sha256_file(path) != item.get("sha256"):
        errors.append(f"B5 V3 retry input hash mismatch: {role}")
    return path


def verify(release_path: Path, *, require_output_absent: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    try:
        release = load_object(release_path)
    except Exception as error:
        return {"verification_id": QA_ID, "status": "FAIL", "errors": [f"Release load failed: {type(error).__name__}: {error}"]}
    root = release_path.resolve().parents[1]
    if release.get("release_id") != RELEASE_ID:
        errors.append("Unexpected B5 V3 retry release identity")
    if release.get("status") != "FROZEN_EXACT_70_SECOND_ADAPTIVE_HTTP_429_RETRY_FINAL_TRIGGER_ROW_ATTEMPT":
        errors.append("Unexpected B5 V3 retry release status")
    inputs = release.get("inputs", {})
    paths = {role: _check_file(root, item, role, errors) for role, item in inputs.items()}

    plan = _read_jsonl(paths["availability_plan"]) if paths.get("availability_plan", Path()).is_file() else []
    expected_ids = [f"TTCV1_B3_AVAIL_{index:03d}" for index in range(1, 71)]
    development = sum(row.get("cohort") == "DEVELOPMENT" for row in plan)
    holdout = sum(row.get("cohort") == "EXTERNAL_HOLDOUT" for row in plan)
    if len(plan) != 70 or [row.get("availability_plan_id") for row in plan] != expected_ids:
        errors.append("B5 V3 retry plan identity/order is not exact 70")
    identity = release.get("identity_contract", {})
    if (development, holdout) != (50, 20) or identity.get("triggering_availability_plan_id") != expected_ids[0] or identity.get("same_previous_release_rerun") is not False:
        errors.append("B5 V3 retry identity/cohort contract changed")

    previous_release_path = paths.get("previous_release", Path())
    previous_release_qa_path = paths.get("previous_release_qa", Path())
    previous_report_path = paths.get("previous_report", Path())
    previous_result_qa_path = paths.get("previous_result_qa", Path())
    if previous_release_path.is_file():
        previous_release_check = verify_v2_release(previous_release_path, require_output_absent=False)
        if previous_release_check.get("status") != V2_RELEASE_PASS_STATUS or previous_release_check.get("errors"):
            errors.append("Previous V2 retry release no longer verifies")
    if previous_release_qa_path.is_file():
        previous_release_qa = load_object(previous_release_qa_path)
        if previous_release_qa.get("status") != inputs.get("previous_release_qa", {}).get("required_status") or previous_release_qa.get("errors") != []:
            errors.append("Previous V2 retry release QA is not authoritative PASS")
    if previous_release_path.is_file() and previous_release_qa_path.is_file() and previous_report_path.is_file():
        previous_result_check = verify_v2_result(previous_release_path, previous_release_qa_path, previous_report_path)
        if previous_result_check.get("status") != V2_RESULT_PARTIAL_STATUS or previous_result_check.get("errors"):
            errors.append("Previous V2 retry result no longer verifies")
        if previous_result_qa_path.is_file() and load_object(previous_result_qa_path) != previous_result_check:
            errors.append("Stored previous V2 retry result QA differs from recomputation")

    try:
        initial = load_object(paths["initial_report"])
        previous = load_object(previous_report_path)
        initial_first = initial["results"][0]
        previous_first = previous["results"][0]
        if any(report.get("logical_attempt_count") != 1 or report.get("network_request_count") != 1 or report.get("stopped_on_http_429") is not True for report in (initial, previous)):
            errors.append("Two prior B5 reports do not each preserve one HTTP 429 attempt")
        if any(row.get("availability_plan_id") != expected_ids[0] or row.get("snapshot_http_status") != "429" for row in (initial_first, previous_first)):
            errors.append("Two prior B5 trigger rows are not the same frozen first-row HTTP 429")
        headers = previous_first.get("response_diagnostics", {}).get("response_headers", {})
        if headers.get("Retry-After") is not None:
            errors.append("Second B5 HTTP 429 unexpectedly contains Retry-After")
        retry_after = headers.get("Retry-After")
    except (KeyError, IndexError, TypeError, OSError, json.JSONDecodeError) as error:
        retry_after = None
        errors.append(f"Prior B5 trigger evidence is invalid: {type(error).__name__}: {error}")

    policy = release.get("retry_policy", {})
    try:
        recomputed = decide(
            failure_class="HTTP_429", observed_at=str(policy["observed_at"]),
            network_attempts=int(policy["network_attempts_for_triggering_row"]),
            consecutive_failures=int(policy["consecutive_failures"]), retry_after=retry_after,
        )
        for field in ("policy_id", "failure_class", "action", "not_before"):
            if policy.get(field) != recomputed.get(field):
                errors.append(f"B5 V3 adaptive retry decision mismatch: {field}")
        if policy.get("policy_id") != POLICY_ID or policy.get("maximum_network_attempts_per_artifact_family") != MAX_NETWORK_ATTEMPTS_PER_ARTIFACT:
            errors.append("B5 V3 adaptive retry policy identity/budget changed")
        if policy.get("network_attempts_for_triggering_row") != 2 or policy.get("consecutive_failures") != 2:
            errors.append("B5 V3 retry is not the third trigger-row attempt")
        if policy.get("triggering_row_identical_retry_after_this_release_if_failed") is not False or policy.get("universal_fixed_24h_retry_forbidden") is not True:
            errors.append("B5 V3 terminal trigger-row policy changed")
        if datetime.fromisoformat(str(policy["not_before"])).tzinfo is None:
            errors.append("B5 V3 retry not-before lacks timezone")
    except (KeyError, TypeError, ValueError) as error:
        errors.append(f"B5 V3 adaptive retry policy is invalid: {type(error).__name__}: {error}")

    contract = release.get("execution_contract", {})
    expected_contract = {
        "endpoint": "https://archive.org/wayback/available", "expected_candidate_count": 70,
        "expected_development_count": 50, "expected_external_holdout_count": 20,
        "minimum_delay_seconds": 60.0, "maximum_attempts_per_candidate": 1,
        "timeout_seconds": 30, "maximum_redirects": 3, "maximum_response_bytes": 2097152,
        "required_content_type_prefix": "application/json", "descriptive_user_agent_required": True,
        "partial_journal_reserved_before_network": True, "partial_journal_auto_resume_allowed": False,
        "stop_on_http_429": True, "stop_on_any_http_or_transport_error": True,
        "errors_are_preserved": True, "errors_are_not_interpreted_as_no_snapshot": True,
        "output_overwrite_allowed": False,
    }
    for field, expected in expected_contract.items():
        if contract.get(field) != expected:
            errors.append(f"B5 V3 execution contract changed: {field}")
    if set(contract.get("allowed_network_hosts", [])) != {"archive.org", "web.archive.org"} or contract.get("preserved_response_headers") != PRESERVED_HEADERS:
        errors.append("B5 V3 archive allowlist or diagnostic headers changed")
    decision = release.get("decision", {})
    if decision.get("retry_allowed_at_or_after_not_before") is not True or decision.get("previous_release_rerun_allowed") is not False:
        errors.append("B5 V3 decision does not isolate the new release")
    for gate in ("candidate_live_domain_access_allowed", "archived_page_download_allowed", "artifact_capture_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "model_scoring_allowed", "training_allowed"):
        if decision.get(gate) is not False:
            errors.append(f"B5 V3 forbidden gate opened: {gate}")

    output = Path(str(release.get("planned_output", {}).get("path", "")))
    partial = output.with_suffix(output.suffix + str(release.get("planned_output", {}).get("partial_journal_suffix", ".partial")))
    if require_output_absent and (output.exists() or partial.exists()):
        errors.append("B5 V3 final or partial output already exists")
    return {
        "verification_id": QA_ID,
        "status": PASS_STATUS if not errors else "FAIL",
        "release": {"path": str(release_path.resolve()), "sha256": sha256_file(release_path)},
        "checks": {"plan_rows": len(plan), "development_rows": development, "external_holdout_rows": holdout, "prior_trigger_row_attempts": 2, "prior_http_429_without_retry_after": retry_after is None, "adaptive_policy_id": policy.get("policy_id"), "not_before": policy.get("not_before"), "output_absent": not output.exists() and not partial.exists(), "network_operations": 0},
        "decision": {"release_prepared": not errors, "retry_allowed_at_or_after_not_before": not errors, "another_identical_trigger_row_retry_if_failed": False, "capture_allowed": False, "training_allowed": False},
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
            raise FileExistsError("Refusing to overwrite B5 V3 retry release QA")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
