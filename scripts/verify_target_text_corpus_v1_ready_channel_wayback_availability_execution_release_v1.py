"""Independently verify B4's exact-70 crash-safe availability execution release."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


RELEASE_ID = "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_WAYBACK_AVAILABILITY_EXECUTION_RELEASE_V1"
PASS_STATUS = "PASS_B4_EXACT_70_EXECUTION_RELEASE_PREPARED_DYNAMIC_A1_COOLDOWN_REQUIRED"
PRESERVED_HEADERS = ["Retry-After", "Date", "Server", "Content-Type", "X-Archive-Wayback-Runtime-Error"]


def resolved(root: Path, item: dict[str, Any]) -> Path:
    path = Path(item["path"])
    return path if path.is_absolute() or item.get("absolute") else root / path


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Timestamp lacks timezone")
    return parsed


def verify(release_path: Path, *, require_output_absent: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    try:
        release = load_object(release_path)
    except Exception as error:
        return {"verification_id": "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_WAYBACK_AVAILABILITY_EXECUTION_RELEASE_QA_V1", "status": "FAIL", "errors": [f"Release load failed: {type(error).__name__}: {error}"]}
    root = release_path.resolve().parents[1]
    if release.get("release_id") != RELEASE_ID:
        errors.append("Unexpected B4 execution release identity")
    if release.get("status") != "FROZEN_CRASH_SAFE_EXACT_70_EXECUTION_RELEASE_DYNAMIC_A1_COOLDOWN_NETWORK_CLOSED":
        errors.append("Unexpected B4 execution release status")
    for item in release.get("basis", []):
        path = resolved(root, item)
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            errors.append(f"B4 basis mismatch: {item.get('role')}")
    for role, item in release.get("inputs", {}).items():
        path = resolved(root, item)
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            errors.append(f"B4 input mismatch: {role}")

    plan_item = release.get("inputs", {}).get("availability_plan", {})
    plan_path = resolved(root, plan_item) if plan_item else Path("__missing__")
    plan = read_jsonl(plan_path) if plan_path.is_file() else []
    if len(plan) != 70 or plan_item.get("record_count") != 70:
        errors.append("B4 plan does not contain exactly 70 rows")
    if [row.get("availability_plan_id") for row in plan] != [f"TTCV1_B3_AVAIL_{index:03d}" for index in range(1, 71)]:
        errors.append("B4 plan identity/order changed")
    plan_qa_item = release.get("inputs", {}).get("independent_plan_qa", {})
    plan_qa_path = resolved(root, plan_qa_item) if plan_qa_item else Path("__missing__")
    if plan_qa_path.is_file():
        plan_qa = load_object(plan_qa_path)
        if plan_qa.get("status") != plan_qa_item.get("required_status") or plan_qa.get("errors") != []:
            errors.append("B3 independent plan QA is not PASS")

    coordination = release.get("coordination_contract", {})
    try:
        a1_release_item = release["inputs"]["a1_cdx_release"]
        a1_release_path = resolved(root, a1_release_item)
        a1_release = load_object(a1_release_path)
        a1_not_before = parse_time(a1_release["cooldown_contract"]["not_before"])
        floor = parse_time(coordination["absolute_not_before_floor"])
        if floor < a1_not_before + timedelta(seconds=int(coordination["minimum_cooldown_seconds_after_latest_archive_request"])):
            errors.append("B4 absolute floor is less than 24 hours after the scheduled A1 gate")
    except Exception as error:
        errors.append(f"B4 coordination time contract is invalid: {type(error).__name__}: {error}")
    if coordination.get("a1_final_report_required_at_execution") is not True:
        errors.append("B4 does not require the final A1 report")
    if coordination.get("a1_independent_result_qa_required_at_execution") is not True:
        errors.append("B4 does not require independent A1 result QA")
    if coordination.get("a1_error_or_http_429_keeps_b4_closed") is not True:
        errors.append("B4 does not fail closed on an A1 error or HTTP 429")
    if coordination.get("dynamic_not_before_rule") != "MAX_ABSOLUTE_FLOOR_AND_A1_REPORT_CREATED_AT_PLUS_86400_SECONDS":
        errors.append("B4 dynamic not-before rule changed")

    contract = release.get("execution_contract", {})
    expected = {
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
        "errors_are_not_interpreted_as_no_snapshot": True,
        "output_overwrite_allowed": False,
    }
    for field, value in expected.items():
        if contract.get(field) != value:
            errors.append(f"B4 execution contract changed: {field}")
    if set(contract.get("allowed_network_hosts", [])) != {"archive.org", "web.archive.org"}:
        errors.append("B4 archive host allowlist changed")
    if contract.get("preserved_response_headers") != PRESERVED_HEADERS:
        errors.append("B4 preserved diagnostic headers changed")

    decision = release.get("decision", {})
    if decision.get("network_execution_allowed_at_release_time") is not False:
        errors.append("B4 release improperly opens network immediately")
    if decision.get("availability_execution_allowed_only_after_dynamic_gate") is not True:
        errors.append("B4 dynamic execution gate is not required")
    for gate in ("candidate_live_domain_access_allowed", "archived_page_download_allowed", "artifact_capture_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "model_scoring_allowed", "training_allowed"):
        if decision.get(gate) is not False:
            errors.append(f"B4 forbidden gate opened: {gate}")
    output = Path(release.get("planned_output", {}).get("path", ""))
    partial = output.with_suffix(output.suffix + str(release.get("planned_output", {}).get("partial_journal_suffix", ".partial")))
    if require_output_absent and (output.exists() or partial.exists()):
        errors.append("B4 final or partial output already exists")

    return {
        "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_WAYBACK_AVAILABILITY_EXECUTION_RELEASE_QA_V1",
        "status": PASS_STATUS if not errors else "FAIL",
        "release": {"path": str(release_path.resolve()), "sha256": sha256_file(release_path)},
        "checks": {
            "plan_rows": len(plan),
            "absolute_not_before_floor": coordination.get("absolute_not_before_floor"),
            "dynamic_a1_report_gate_required": coordination.get("a1_final_report_required_at_execution"),
            "minimum_delay_seconds": contract.get("minimum_delay_seconds"),
            "maximum_attempts_per_candidate": contract.get("maximum_attempts_per_candidate"),
            "partial_journal_required": contract.get("partial_journal_reserved_before_network"),
            "stop_on_http_429": contract.get("stop_on_http_429"),
            "network_execution_allowed_now": False,
        },
        "decision": {"release_prepared": not errors, "execution_requires_dynamic_a1_cooldown": True, "network_execution_allowed_now": False, "capture_allowed": False, "training_allowed": False},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "candidate_domain_access_operations": 0, "wayback_queries": 0, "archived_page_downloads": 0, "captures": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False},
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
            raise FileExistsError("Refusing to overwrite B4 release QA")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
