"""Verify the residual V1-Core acquisition wave plan V2."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def verify(path: Path) -> dict[str, Any]:
    plan = load_object(path)
    root = path.resolve().parents[1]
    errors: list[str] = []
    if plan.get("plan_id") != "ISI_TARGET_TEXT_CORPUS_V1_ACQUISITION_WAVE_PLAN_V2" or plan.get("status") != "FROZEN_OFFLINE_PLAN_SOURCE_GATES_REMAIN_CLOSED":
        errors.append("Unexpected plan identity or status")
    for item in plan.get("inputs", []):
        source = root / item["path"]
        if not source.is_file() or sha256_file(source) != item["sha256"]:
            errors.append(f"Input hash mismatch: {item.get('role')}")
    waves = {row.get("channel_id"): row for row in plan.get("waves", [])}
    expected = {
        "CONFIRMED_REGULATOR_LINKED_WEBSITE": (60, 15, 0),
        "CONFIRMED_CFTC_RED_LINKED_WAYBACK_WEBSITE": (60, 15, 0),
        "LEGITIMATE_REGISTER_LINKED_WEBSITE": (60, 15, 0),
        "LEGITIMATE_SEC_EDGAR_LINKED_WAYBACK_WEBSITE": (27, 6, 42),
    }
    if set(waves) != set(expected):
        errors.append("Wave channel population changed")
    for channel, values in expected.items():
        row = waves.get(channel, {})
        if (row.get("development_accepted_target"), row.get("external_holdout_accepted_target"), row.get("current_owner_accepted_supply")) != values:
            errors.append(f"Wave targets changed: {channel}")
        if row.get("network_release_allowed_now") is not False:
            errors.append(f"Wave prematurely opens network: {channel}")
    selection = plan.get("selection_contract", {})
    if selection.get("development_namespace") == selection.get("external_holdout_namespace") or selection.get("namespace_reuse_allowed") is not False:
        errors.append("Development/holdout namespaces are not disjoint")
    for gate in ("candidate_enumeration_allowed", "network_execution_allowed", "capture_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "model_scoring_allowed", "training_allowed"):
        if plan.get("decision", {}).get(gate) is not False:
            errors.append(f"Plan opened forbidden gate: {gate}")
    return {"verification_id": "ISI_TARGET_TEXT_CORPUS_V1_ACQUISITION_WAVE_PLAN_QA_V2", "status": "PASS_OFFLINE_WAVE_PLAN_SOURCE_GATES_CLOSED" if not errors else "FAIL", "inputs": {"plan_sha256": sha256_file(path)}, "checks": {"channel_count": len(waves), "development_residual_target": sum(row.get("development_accepted_target", 0) for row in waves.values()), "external_holdout_residual_target": sum(row.get("external_holdout_accepted_target", 0) for row in waves.values()), "owner_accepted_candidate_supply": sum(row.get("current_owner_accepted_supply", 0) for row in waves.values())}, "decision": {"plan_verified": not errors, "enumeration_release_may_be_prepared_per_ready_channel": not errors, "network_allowed_now": False, "training_allowed": False}, "errors": errors, "safety_contract": {"network_operations": 0, "labels": 0, "model": 0}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.plan)
    if args.output:
        if args.output.exists():
            raise FileExistsError("Refusing to overwrite wave-plan QA")
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
