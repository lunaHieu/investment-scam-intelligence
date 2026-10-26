"""Execute the exact-69 B5 continuation after the circuit-breaker gate."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.execute_target_text_corpus_v1_ready_channel_wayback_availability_v1 import run_plan
from scripts.verify_target_text_corpus_v1_ready_channel_wayback_availability_continuation_release_v1 import PASS_STATUS, continuation_plan, read_plan, verify as verify_release
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


EXECUTOR = "scripts.execute_target_text_corpus_v1_ready_channel_wayback_availability_continuation_v1"


def validate(release_path: Path, release_qa_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    recomputed = verify_release(release_path, require_output_absent=True)
    release, qa = load_object(release_path), load_object(release_qa_path)
    if recomputed.get("status") != PASS_STATUS or recomputed.get("errors"):
        raise PermissionError("B5 continuation release independent recomputation failed")
    if qa != recomputed or qa.get("release", {}).get("sha256") != sha256_file(release_path):
        raise PermissionError("B5 continuation release QA is not authoritative PASS")
    source = read_plan(Path(str(release["inputs"]["availability_plan"]["path"])))
    return release, continuation_plan(release, source)


def coordination_evidence(release: dict[str, Any], current: datetime) -> dict[str, Any]:
    if current.tzinfo is None:
        raise ValueError("B5 continuation current time must include timezone")
    gate = datetime.fromisoformat(str(release["circuit_breaker_policy"]["not_before"]))
    if current < gate:
        raise PermissionError(f"B5 continuation circuit breaker is open until {gate.isoformat()}")
    inputs, policy = release["inputs"], release["circuit_breaker_policy"]
    return {"coordination_policy": policy["policy_id"], "endpoint_consecutive_failures_before_release": policy["endpoint_consecutive_failures"], "continuation_rows_prior_network_attempts": 0, "v3_report_path": inputs["v3_report"]["path"], "v3_report_sha256": inputs["v3_report"]["sha256"], "v3_result_qa_path": inputs["v3_result_qa"]["path"], "v3_result_qa_sha256": inputs["v3_result_qa"]["sha256"], "quarantined_availability_plan_ids": release["quarantine_contract"]["excluded_availability_plan_ids"], "not_before": gate.isoformat(), "universal_fixed_24h_retry_forbidden": True, "authoritative_wrapper": EXECUTOR, "immutable_runner": "scripts.execute_target_text_corpus_v1_ready_channel_wayback_availability_v1.run_plan"}


def execute(release_path: Path, release_qa_path: Path, now: datetime | None = None) -> dict[str, Any]:
    release, plan = validate(release_path, release_qa_path)
    current = now or datetime.now(timezone.utc).astimezone()
    return run_plan(release_path, release_qa_path, release, plan, Path(str(release["planned_output"]["path"])), current.isoformat(), coordination_evidence(release, current))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-qa", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    release, plan = validate(args.release, args.release_qa)
    current = datetime.now(timezone.utc).astimezone()
    coordination = coordination_evidence(release, current)
    if args.verify_only:
        print(json.dumps({"valid": True, "release_id": release["release_id"], "continuation_rows": len(plan), "first_id": plan[0]["availability_plan_id"], "gate_open": True, "not_before": coordination["not_before"], "quarantined_ids": coordination["quarantined_availability_plan_ids"], "network_execution_performed": False}, ensure_ascii=False, indent=2))
        return 0
    report = execute(args.release, args.release_qa, now=current)
    print(json.dumps({key: report[key] for key in ("report_id", "status", "requested_candidate_count", "logical_attempt_count", "network_request_count", "available_snapshot_count", "unavailable_snapshot_count", "unresolved_error_count", "stopped_on_http_429", "capture_plan_construction_ready")}, ensure_ascii=False, indent=2))
    return 0 if report["capture_plan_construction_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
