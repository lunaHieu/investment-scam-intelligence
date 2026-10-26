"""Run B5 through the canonical-empty-aware V2 coordination amendment."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.execute_target_text_corpus_v1_ready_channel_wayback_availability_v1 import (
    run_plan,
    validate_static_inputs,
)
from scripts.verify_target_text_corpus_v1_ready_channel_wayback_availability_execution_amendment_v2 import (
    PASS_STATUS,
    verify as verify_amendment,
)
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


EXECUTOR = "scripts.execute_target_text_corpus_v1_ready_channel_wayback_availability_v2"


def validate(
    release_path: Path,
    release_qa_path: Path,
    amendment_path: Path,
    amendment_qa_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    release, plan = validate_static_inputs(release_path, release_qa_path)
    amendment = load_object(amendment_path)
    amendment_qa = load_object(amendment_qa_path)
    recomputed = verify_amendment(amendment_path, require_output_absent=True)
    if recomputed.get("status") != PASS_STATUS or recomputed.get("errors"):
        raise PermissionError("B5 V2 amendment independent recomputation failed")
    if amendment_qa != recomputed or amendment_qa.get("amendment", {}).get("sha256") != sha256_file(amendment_path):
        raise PermissionError("B5 V2 amendment QA is not authoritative PASS")
    parent = amendment.get("parent_release", {})
    parent_qa = amendment.get("parent_release_qa", {})
    if parent.get("sha256") != sha256_file(release_path) or parent_qa.get("sha256") != sha256_file(release_qa_path):
        raise PermissionError("B5 V2 parent release binding changed")
    return release, plan, amendment


def coordination_evidence(amendment: dict[str, Any], current: datetime) -> dict[str, Any]:
    gate = datetime.fromisoformat(str(amendment["coordination_contract"]["effective_not_before"]))
    if current.tzinfo is None:
        raise ValueError("B5 V2 current time must include timezone")
    if current < gate:
        raise PermissionError(f"B5 V2 coordination gate is closed until {gate.isoformat()}")
    evidence = amendment["a1_canonical_empty_evidence"]
    return {
        "coordination_policy": "A1_CANONICAL_EMPTY_HTTP_200_TERMINAL_NONBLOCKING_V2",
        "a1_report_path": evidence["execution_report"]["path"],
        "a1_report_sha256": evidence["execution_report"]["sha256"],
        "a1_result_qa_path": evidence["v2_result_qa"]["path"],
        "a1_result_qa_sha256": evidence["v2_result_qa"]["sha256"],
        "a1_root_cause": "PARSER_DID_NOT_ACCEPT_VALID_ZERO_ROW_CDX_JSON",
        "a1_rate_limit": False,
        "a1_retry_needed": False,
        "effective_not_before": gate.isoformat(),
        "adaptive_retry_policy": "ISI_ARCHIVE_RETRY_POLICY_V1",
        "authoritative_wrapper": EXECUTOR,
    }


def execute(
    release_path: Path,
    release_qa_path: Path,
    amendment_path: Path,
    amendment_qa_path: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    release, plan, amendment = validate(release_path, release_qa_path, amendment_path, amendment_qa_path)
    current = now or datetime.now(timezone.utc).astimezone()
    coordination = coordination_evidence(amendment, current)
    return run_plan(
        release_path, release_qa_path, release, plan,
        Path(str(release["planned_output"]["path"])), current.isoformat(), coordination,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-qa", type=Path, required=True)
    parser.add_argument("--amendment", type=Path, required=True)
    parser.add_argument("--amendment-qa", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    release, plan, amendment = validate(args.release, args.release_qa, args.amendment, args.amendment_qa)
    current = datetime.now(timezone.utc).astimezone()
    coordination = coordination_evidence(amendment, current)
    if args.verify_only:
        print(json.dumps({"valid": True, "release_id": release["release_id"], "plan_rows": len(plan), "gate_open": True, "coordination_policy": coordination["coordination_policy"], "authoritative_wrapper": EXECUTOR, "network_execution_performed": False}, ensure_ascii=False, indent=2))
        return 0
    report = execute(args.release, args.release_qa, args.amendment, args.amendment_qa, now=current)
    print(json.dumps({key: report[key] for key in ("report_id", "status", "requested_candidate_count", "logical_attempt_count", "network_request_count", "available_snapshot_count", "unavailable_snapshot_count", "unresolved_error_count", "stopped_on_http_429", "capture_plan_construction_ready")}, ensure_ascii=False, indent=2))
    return 0 if report["capture_plan_construction_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
