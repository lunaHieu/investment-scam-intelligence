"""Independently verify C1's offline-only parallel workstream scope."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


EXPECTED_PLAN_ID = "ISI_TARGET_TEXT_CORPUS_V1_PARALLEL_C_WORKSTREAM_V1"


def _resolved(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def verify(config_path: Path) -> dict[str, Any]:
    config = load_object(config_path)
    errors: list[str] = []
    if config.get("plan_id") != EXPECTED_PLAN_ID:
        errors.append("Unexpected C1 plan ID")
    root = config_path.resolve().parents[1]
    inputs: dict[str, dict[str, Any]] = {}
    for item in config.get("inputs", []):
        path = _resolved(root, item["path"])
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            errors.append(f"C1 input mismatch: {item['role']}")
            continue
        inputs[item["role"]] = load_object(path)
    required = {"sampling_matrix", "capacity_gap_v4", "acquisition_wave_plan_v2", "manual_acquisition_packet_v1", "vietnamese_terms_v1", "a5_packets_v1", "b4_execution_v1"}
    if set(inputs) != required:
        errors.append("C1 input roles are incomplete")
    if errors:
        return _result(config_path, config, errors)

    capacity = inputs["capacity_gap_v4"]
    totals = capacity.get("capacity_matrix", {}).get("totals", {})
    boundary = config["capacity_boundary"]
    expected_boundary = {
        "required_groups": totals.get("required"),
        "admitted_groups": totals.get("admitted"),
        "conditional_owner_accepted_supply": totals.get("conditional_supply"),
        "conditional_residual_gap": totals.get("conditional_gap"),
        "audited_language_credit": capacity.get("language_overlay", {}).get("audited_language_credit"),
        "required_vietnamese_groups": capacity.get("language_overlay", {}).get("required_vietnamese_groups"),
    }
    if boundary != expected_boundary:
        errors.append("C1 capacity boundary differs from current V4 recomputation")
    matrix = inputs["sampling_matrix"]
    if matrix.get("release_target", {}).get("total_groups") not in (None, 300):
        errors.append("C1 sampling matrix target changed")
    wave = inputs["acquisition_wave_plan_v2"]
    if wave.get("result", {}).get("cftc_channel_blocked") is not True or wave.get("decision", {}).get("network_allowed_now") is not False:
        errors.append("C1 does not preserve the frozen CFTC/network gate")
    manual = inputs["manual_acquisition_packet_v1"]
    findings = manual.get("findings", {})
    if findings.get("source_count") != 3 or manual.get("decision", {}).get("source_files_acquired") != 0:
        errors.append("C1 manual-source state differs from frozen packet")
    vietnamese = inputs["vietnamese_terms_v1"]
    if vietnamese.get("decision", {}).get("reference_acquisition_gate_passed") is not False or vietnamese.get("findings", {}).get("reference_records_acquired") != 0:
        errors.append("C1 Vietnamese acquisition gate was opened")
    a5 = inputs["a5_packets_v1"]
    if a5.get("result", {}).get("fresh_cohort_assertions_independently_verified") != 42 or a5.get("result", {}).get("language_records_pending_human_review") != 42 or a5.get("decision", {}).get("human_language_review_complete") is not False:
        errors.append("C1 A5 state differs from current exact-42 packets")
    b4 = inputs["b4_execution_v1"]
    if b4.get("result", {}).get("network_requests_executed") != 0 or b4.get("decision", {}).get("network_execution_allowed_now") is not False:
        errors.append("C1 does not preserve B4/B5 isolation")

    scope = {item["source_or_task"]: item for item in config.get("c1_scope", [])}
    expected_scope = {"CFTC_RED_REFERENCE_CAPACITY", "DFPI_FIRST_PARTY_OR_OFFICIAL_EXPORT", "SSC_VIETNAM_CONFIRMED_REFERENCE", "HNX_VIETNAM_LEGITIMATE_REFERENCE", "A5_EXACT_42_LANGUAGE_REVIEW"}
    if set(scope) != expected_scope or any(item.get("network_allowed") is not False for item in scope.values()):
        errors.append("C1 scope is incomplete or permits network access")
    if scope.get("CFTC_RED_REFERENCE_CAPACITY", {}).get("target_groups") != 75 or scope.get("A5_EXACT_42_LANGUAGE_REVIEW", {}).get("target_groups") != 42:
        errors.append("C1 bounded target counts changed")
    if len(config.get("ordered_follow_on_gates", [])) != 3 or [item.get("gate") for item in config["ordered_follow_on_gates"]] != ["C2_EXTERNAL_ARTIFACT_INTAKE", "C3_LANGUAGE_REVIEW_RESPONSE", "C4_MATRIX_AND_ENUMERATION_RELEASE"]:
        errors.append("C1 follow-on gate order changed")
    isolation = config.get("branch_isolation", {})
    if any(isolation.get(field) is not False for field in isolation):
        errors.append("C1 branch isolation permits a forbidden mutation")
    for gate in ("external_artifact_intake_execution_allowed_without_artifact", "candidate_enumeration_allowed", "network_execution_allowed", "candidate_domain_access_allowed", "capture_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "model_scoring_allowed", "training_allowed"):
        if config.get("decision", {}).get(gate) is not False:
            errors.append(f"C1 opened forbidden gate: {gate}")
    safety = config.get("safety_contract", {})
    if any(safety.get(field) not in (0, False) for field in safety):
        errors.append("C1 safety contract records an operation or open gate")
    return _result(config_path, config, errors)


def _result(config_path: Path, config: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    boundary = config.get("capacity_boundary", {})
    return {
        "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_PARALLEL_C_WORKSTREAM_QA_V1",
        "status": "PASS_C1_OFFLINE_SCOPE_FROZEN_EXTERNAL_GATES_PRESERVED" if not errors else "FAIL",
        "inputs": {"plan_sha256": sha256_file(config_path)},
        "checks": {"scope_items": len(config.get("c1_scope", [])), "ordered_follow_on_gates": len(config.get("ordered_follow_on_gates", [])), "required_groups": boundary.get("required_groups"), "admitted_groups": boundary.get("admitted_groups"), "conditional_residual_gap": boundary.get("conditional_residual_gap")},
        "decision": {"c1_scope_qa_passed": not errors, "external_artifact_or_human_input_still_required": True, "network_execution_allowed": False, "training_allowed": False},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "source_files_acquired": 0, "candidate_records_enumerated": 0, "captures": 0, "labels_changed": 0, "model_operations": 0, "training_allowed": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    result = verify(args.config)
    if args.verify_only:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if not result["errors"] else 1
    if args.output is None:
        raise ValueError("--output is required unless --verify-only is used")
    expected = Path(load_object(args.config)["planned_output"]["independent_qa"])
    if args.output.resolve() != expected.resolve():
        raise ValueError("C1 QA output path differs from frozen plan")
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite C1 QA")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
