"""Verify the exact-69 B5 continuation after trigger-row quarantine."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.archive_retry_policy_v1 import POLICY_ID, decide
from scripts.verify_target_text_corpus_v1_ready_channel_wayback_availability_retry_release_v3 import PASS_STATUS as V3_RELEASE_PASS_STATUS, PRESERVED_HEADERS, verify as verify_v3_release
from scripts.verify_target_text_corpus_v1_ready_channel_wayback_availability_retry_result_v3 import PARTIAL_STATUS as V3_RESULT_PARTIAL_STATUS, verify as verify_v3_result
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


RELEASE_ID = "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_WAYBACK_AVAILABILITY_CONTINUATION_RELEASE_V1"
QA_ID = "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_WAYBACK_AVAILABILITY_CONTINUATION_RELEASE_QA_V1"
PASS_STATUS = "PASS_B5_EXACT_69_CONTINUATION_TRIGGER_ROW_QUARANTINED_CIRCUIT_BREAKER"


def _resolve(root: Path, item: dict[str, Any]) -> Path:
    path = Path(str(item.get("path", "")))
    return path if path.is_absolute() else root / path


def read_plan(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def continuation_plan(release: dict[str, Any], plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    excluded = set(release["quarantine_contract"]["excluded_availability_plan_ids"])
    return [row for row in plan if row["availability_plan_id"] not in excluded]


def verify(release_path: Path, *, require_output_absent: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    try:
        release = load_object(release_path)
    except Exception as error:
        return {"verification_id": QA_ID, "status": "FAIL", "errors": [f"Release load failed: {type(error).__name__}: {error}"]}
    root = release_path.resolve().parents[1]
    if release.get("release_id") != RELEASE_ID or release.get("status") != "FROZEN_EXACT_69_CONTINUATION_AFTER_TRIGGER_ROW_QUARANTINE_ENDPOINT_CIRCUIT_BREAKER":
        errors.append("Unexpected B5 continuation release identity/status")
    paths: dict[str, Path] = {}
    for role, item in release.get("inputs", {}).items():
        path = _resolve(root, item)
        paths[role] = path
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            errors.append(f"B5 continuation input hash mismatch: {role}")

    source = read_plan(paths["availability_plan"]) if paths.get("availability_plan", Path()).is_file() else []
    plan = continuation_plan(release, source) if source else []
    expected_ids = [f"TTCV1_B3_AVAIL_{index:03d}" for index in range(2, 71)]
    development = sum(row.get("cohort") == "DEVELOPMENT" for row in plan)
    holdout = sum(row.get("cohort") == "EXTERNAL_HOLDOUT" for row in plan)
    if len(source) != 70 or len(plan) != 69 or [row.get("availability_plan_id") for row in plan] != expected_ids:
        errors.append("B5 continuation is not the ordered exact 69 after excluding row 001")
    quarantine = release.get("quarantine_contract", {})
    if quarantine.get("excluded_availability_plan_ids") != ["TTCV1_B3_AVAIL_001"] or quarantine.get("identical_retry_allowed") is not False or quarantine.get("label_inference_allowed") is not False or quarantine.get("project_blocking") is not False:
        errors.append("B5 trigger-row quarantine contract changed")
    identity = release.get("identity_contract", {})
    if (development, holdout) != (49, 20) or identity.get("expected_candidate_count") != 69 or identity.get("expected_first_availability_plan_id") != expected_ids[0] or identity.get("expected_last_availability_plan_id") != expected_ids[-1]:
        errors.append("B5 continuation identity/cohort contract changed")

    if paths.get("v3_release", Path()).is_file():
        check = verify_v3_release(paths["v3_release"], require_output_absent=False)
        if check.get("status") != V3_RELEASE_PASS_STATUS or check.get("errors"):
            errors.append("V3 release no longer verifies")
    if all(paths.get(role, Path()).is_file() for role in ("v3_release", "v3_release_qa", "v3_report")):
        result = verify_v3_result(paths["v3_release"], paths["v3_release_qa"], paths["v3_report"])
        if result.get("status") != V3_RESULT_PARTIAL_STATUS or result.get("errors"):
            errors.append("V3 result no longer proves trigger-row budget exhaustion")
        if paths.get("v3_result_qa", Path()).is_file() and load_object(paths["v3_result_qa"]) != result:
            errors.append("Stored V3 result QA differs from recomputation")
    try:
        report = load_object(paths["v3_report"])
        first = report["results"][0]
        headers = first.get("response_diagnostics", {}).get("response_headers", {})
        if first.get("availability_plan_id") != "TTCV1_B3_AVAIL_001" or first.get("snapshot_http_status") != "429" or headers.get("Retry-After") is not None:
            errors.append("V3 terminal trigger-row HTTP 429 evidence changed")
        retry_after = headers.get("Retry-After")
    except (KeyError, IndexError, TypeError, OSError, json.JSONDecodeError) as error:
        retry_after = None
        errors.append(f"V3 terminal evidence is invalid: {type(error).__name__}: {error}")

    policy = release.get("circuit_breaker_policy", {})
    try:
        recomputed = decide(failure_class="HTTP_429", observed_at=str(policy["observed_at"]), network_attempts=int(policy["continuation_rows_prior_network_attempts"]), consecutive_failures=int(policy["endpoint_consecutive_failures"]), retry_after=retry_after)
        for field in ("policy_id", "failure_class", "action", "not_before"):
            if policy.get(field) != recomputed.get(field):
                errors.append(f"B5 circuit-breaker decision mismatch: {field}")
        observed = datetime.fromisoformat(str(policy["observed_at"]))
        gate = datetime.fromisoformat(str(policy["not_before"]))
        if int((gate - observed).total_seconds()) != policy.get("delay_seconds") or policy.get("delay_seconds") != 21600 or policy.get("policy_id") != POLICY_ID:
            errors.append("B5 circuit-breaker six-hour gate changed")
        if policy.get("universal_fixed_24h_retry_forbidden") is not True:
            errors.append("B5 continuation reinstates a universal 24-hour gate")
    except (KeyError, TypeError, ValueError) as error:
        errors.append(f"B5 circuit-breaker policy is invalid: {type(error).__name__}: {error}")

    contract = release.get("execution_contract", {})
    expected = {"endpoint": "https://archive.org/wayback/available", "expected_candidate_count": 69, "expected_development_count": 49, "expected_external_holdout_count": 20, "minimum_delay_seconds": 60.0, "maximum_attempts_per_candidate": 1, "timeout_seconds": 30, "maximum_redirects": 3, "maximum_response_bytes": 2097152, "required_content_type_prefix": "application/json", "descriptive_user_agent_required": True, "partial_journal_reserved_before_network": True, "partial_journal_auto_resume_allowed": False, "stop_on_http_429": True, "stop_on_any_http_or_transport_error": True, "errors_are_preserved": True, "errors_are_not_interpreted_as_no_snapshot": True, "output_overwrite_allowed": False}
    for field, value in expected.items():
        if contract.get(field) != value:
            errors.append(f"B5 continuation execution contract changed: {field}")
    if set(contract.get("allowed_network_hosts", [])) != {"archive.org", "web.archive.org"} or contract.get("preserved_response_headers") != PRESERVED_HEADERS:
        errors.append("B5 continuation archive allowlist or diagnostic headers changed")
    decision = release.get("decision", {})
    if decision.get("continuation_allowed_at_or_after_not_before") is not True or decision.get("quarantined_trigger_row_retry_allowed") is not False:
        errors.append("B5 continuation decision does not preserve quarantine")
    for gate_name in ("candidate_live_domain_access_allowed", "archived_page_download_allowed", "artifact_capture_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "model_scoring_allowed", "training_allowed"):
        if decision.get(gate_name) is not False:
            errors.append(f"B5 continuation forbidden gate opened: {gate_name}")

    output = Path(str(release.get("planned_output", {}).get("path", "")))
    partial = output.with_suffix(output.suffix + str(release.get("planned_output", {}).get("partial_journal_suffix", ".partial")))
    if require_output_absent and (output.exists() or partial.exists()):
        errors.append("B5 continuation final or partial output already exists")
    return {"verification_id": QA_ID, "status": PASS_STATUS if not errors else "FAIL", "release": {"path": str(release_path.resolve()), "sha256": sha256_file(release_path)}, "checks": {"source_rows": len(source), "continuation_rows": len(plan), "development_rows": development, "external_holdout_rows": holdout, "quarantined_ids": quarantine.get("excluded_availability_plan_ids"), "endpoint_consecutive_http_429": policy.get("endpoint_consecutive_failures"), "not_before": policy.get("not_before"), "output_absent": not output.exists() and not partial.exists(), "network_operations": 0}, "decision": {"release_prepared": not errors, "continuation_allowed_at_or_after_not_before": not errors, "quarantined_trigger_row_retry_allowed": False, "capture_allowed": False, "training_allowed": False}, "errors": errors, "safety_contract": {"network_operations": 0, "candidate_domain_access_operations": 0, "archived_page_downloads": 0, "captures": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False}}


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
            raise FileExistsError("Refusing to overwrite B5 continuation release QA")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
