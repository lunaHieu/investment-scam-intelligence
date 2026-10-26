"""Execute the separately frozen second adaptive B5 retry."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.execute_target_text_corpus_v1_ready_channel_wayback_availability_v1 import read_jsonl, run_plan
from scripts.verify_target_text_corpus_v1_ready_channel_wayback_availability_retry_release_v3 import (
    PASS_STATUS,
    verify as verify_release,
)
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


EXECUTOR = "scripts.execute_target_text_corpus_v1_ready_channel_wayback_availability_retry_v3"


def validate(release_path: Path, release_qa_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    recomputed = verify_release(release_path, require_output_absent=True)
    release = load_object(release_path)
    release_qa = load_object(release_qa_path)
    if recomputed.get("status") != PASS_STATUS or recomputed.get("errors"):
        raise PermissionError("B5 V3 retry release independent recomputation failed")
    if release_qa != recomputed:
        raise PermissionError("B5 V3 retry release QA differs from independent recomputation")
    if release_qa.get("release", {}).get("sha256") != sha256_file(release_path):
        raise PermissionError("B5 V3 retry release QA hash binding changed")
    return release, read_jsonl(Path(str(release["inputs"]["availability_plan"]["path"])))


def coordination_evidence(release: dict[str, Any], current: datetime) -> dict[str, Any]:
    if current.tzinfo is None:
        raise ValueError("B5 V3 retry current time must include timezone")
    gate = datetime.fromisoformat(str(release["retry_policy"]["not_before"]))
    if current < gate:
        raise PermissionError(f"B5 V3 adaptive retry gate is closed until {gate.isoformat()}")
    inputs = release["inputs"]
    policy = release["retry_policy"]
    return {
        "coordination_policy": policy["policy_id"],
        "failure_class": policy["failure_class"],
        "consecutive_failures_before_release": policy["consecutive_failures"],
        "network_attempts_before_release": policy["network_attempts_for_triggering_row"],
        "previous_report_path": inputs["previous_report"]["path"],
        "previous_report_sha256": inputs["previous_report"]["sha256"],
        "previous_result_qa_path": inputs["previous_result_qa"]["path"],
        "previous_result_qa_sha256": inputs["previous_result_qa"]["sha256"],
        "retry_after_header": policy["retry_after_header"],
        "not_before": gate.isoformat(),
        "triggering_row_final_attempt": True,
        "universal_fixed_24h_retry_forbidden": policy["universal_fixed_24h_retry_forbidden"],
        "authoritative_wrapper": EXECUTOR,
        "immutable_runner": "scripts.execute_target_text_corpus_v1_ready_channel_wayback_availability_v1.run_plan",
    }


def execute(release_path: Path, release_qa_path: Path, now: datetime | None = None) -> dict[str, Any]:
    release, plan = validate(release_path, release_qa_path)
    current = now or datetime.now(timezone.utc).astimezone()
    return run_plan(
        release_path, release_qa_path, release, plan,
        Path(str(release["planned_output"]["path"])), current.isoformat(),
        coordination_evidence(release, current),
    )


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
        print(json.dumps({"valid": True, "release_id": release["release_id"], "plan_rows": len(plan), "gate_open": True, "not_before": coordination["not_before"], "triggering_row_final_attempt": True, "coordination_policy": coordination["coordination_policy"], "authoritative_wrapper": EXECUTOR, "network_execution_performed": False}, ensure_ascii=False, indent=2))
        return 0
    report = execute(args.release, args.release_qa, now=current)
    print(json.dumps({key: report[key] for key in ("report_id", "status", "requested_candidate_count", "logical_attempt_count", "network_request_count", "available_snapshot_count", "unavailable_snapshot_count", "unresolved_error_count", "stopped_on_http_429", "capture_plan_construction_ready")}, ensure_ascii=False, indent=2))
    return 0 if report["capture_plan_construction_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
