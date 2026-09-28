"""Verify the legitimate second-pass packet and prove downstream gates remain closed."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from validate_external_text_intake import sha256_file


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def resolve_path(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    args = parser.parse_args()
    registry = load_json(args.registry)
    root = args.registry.resolve().parents[2]
    errors: list[str] = []
    checked: list[dict[str, object]] = []

    if registry.get("analysis_id") != "EXTERNAL_TEXT_LEGITIMATE_RECONCILIATION_PACKET_V1":
        errors.append("Unexpected analysis ID")
    if registry.get("status") != "SECOND_PASS_COMPLETE_HUMAN_DECISION_REQUIRED_ZERO_ELIGIBLE":
        errors.append("Unexpected registry status")

    for item in registry.get("implementation", []):
        path = resolve_path(root, item.get("path"))
        actual = sha256_file(path) if path.is_file() else None
        checked.append({"role": item.get("role"), "path": str(path), "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"Implementation artifact missing or changed: {item.get('role')}")

    for role, item in registry.get("inputs", {}).items():
        path = resolve_path(root, item.get("path"))
        actual = sha256_file(path) if path.is_file() else None
        checked.append({"role": role, "path": str(path), "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"Input missing or changed: {role}")

    outputs = {item.get("role"): item for item in registry.get("outputs", [])}
    if set(outputs) != {"decision_packet_json", "decision_packet_markdown"}:
        errors.append("Unexpected output roles")
    for role, item in outputs.items():
        path = resolve_path(root, item.get("path"))
        actual = sha256_file(path) if path.is_file() else None
        checked.append({"role": role, "path": str(path), "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"Output missing or changed: {role}")

    packet_path = resolve_path(root, outputs.get("decision_packet_json", {}).get("path", ""))
    packet = load_json(packet_path) if packet_path.is_file() else {}
    if packet.get("analysis_id") != "EXTERNAL_TEXT_LEGITIMATE_RECONCILIATION_PACKET_V1":
        errors.append("Unexpected packet analysis ID")
    if packet.get("status") != "SECOND_PASS_COMPLETE_HUMAN_DECISION_REQUIRED_ZERO_ELIGIBLE":
        errors.append("Unexpected packet status")

    records = packet.get("records", [])
    if len(records) != 11:
        errors.append("Packet must contain exactly eleven records")
    seen_cases: set[str] = set()
    for record in records:
        case_id = str(record.get("case_id"))
        if case_id in seen_cases:
            errors.append(f"Duplicate packet case: {case_id}")
        seen_cases.add(case_id)
        if record.get("source_state") != {
            "ground_truth_status": "UNCERTAIN",
            "label_confidence": "LOW",
            "review_status": "IN_REVIEW",
            "record_state_changed": False,
        }:
            errors.append(f"Source state is not frozen: {case_id}")
        integrity = record.get("source_integrity", {})
        if integrity.get("raw_capture_hash_valid") is not True:
            errors.append(f"Packet raw integrity failed: {case_id}")
        if integrity.get("normalized_text_hash_valid") is not True:
            errors.append(f"Packet text integrity failed: {case_id}")
        if record.get("contradiction_review", {}).get("hard_contradictions") != []:
            errors.append(f"Hard contradiction remains: {case_id}")
        proposal = record.get("automated_second_pass", {})
        if proposal.get("proposed_outcome_for_human_review") != "LEGITIMATE":
            errors.append(f"Unexpected second-pass proposal: {case_id}")
        if proposal.get("recommendation_is_ground_truth") is not False:
            errors.append(f"Recommendation became ground truth: {case_id}")
        sec = record.get("sec_identity_and_registration", {})
        if sec.get("registration_is_identity_evidence_not_safety_endorsement") is not True:
            errors.append(f"Registration semantics weakened: {case_id}")
        human = record.get("human_decision", {})
        required_empty = (
            "decision",
            "final_confidence",
            "reviewer",
            "reviewed_at",
            "rationale",
            "contradictory_evidence_reviewed",
            "site_control_confirmed",
        )
        if any(human.get(field) is not None for field in required_empty):
            errors.append(f"Human decision was pre-filled: {case_id}")
        if human.get("eligible_for_external_evaluation") is not False:
            errors.append(f"Human gate was opened: {case_id}")
        if record.get("external_evaluation_eligible") is not False:
            errors.append(f"External evaluation gate was opened: {case_id}")

    coverage = packet.get("coverage", {})
    expected_coverage = {
        "record_count": 11,
        "raw_capture_hash_valid_count": 11,
        "normalized_text_hash_valid_count": 11,
        "all_automatic_gates_pass_count": 11,
        "hard_contradiction_case_count": 0,
        "legitimate_proposal_for_human_review_count": 11,
        "high_recommendation_count": 6,
        "medium_high_recommendation_count": 5,
        "human_decision_count": 0,
        "external_evaluation_eligible_count": 0,
        "labels_created": 0,
    }
    if coverage != expected_coverage:
        errors.append("Packet coverage differs from the frozen contract")

    raw_root = Path(str(packet.get("inputs", {}).get("raw_root", "")))
    source_records: dict[str, dict[str, object]] = {}
    for item in packet.get("inputs", {}).get("intakes", []):
        path = Path(str(item.get("path", "")))
        actual = sha256_file(path) if path.is_file() else None
        if actual != item.get("sha256"):
            errors.append(f"Packet intake input missing or changed: {path}")
            continue
        for record in load_json(path).get("records", []):
            case_id = str(record.get("case_id"))
            if case_id in source_records:
                errors.append(f"Duplicate source case: {case_id}")
            source_records[case_id] = record
    for item in packet.get("inputs", {}).get("first_pass_reports", []):
        path = Path(str(item.get("path", "")))
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            errors.append(f"Packet first-pass input missing or changed: {path}")
    if set(source_records) != seen_cases:
        errors.append("Packet/source case sets differ")
    for case_id, record in source_records.items():
        if (
            record.get("ground_truth_status") != "UNCERTAIN"
            or record.get("label_confidence") != "LOW"
            or record.get("review_status") != "IN_REVIEW"
        ):
            errors.append(f"Source intake state changed: {case_id}")
        if any(item.get("reviewed") is not False for item in record.get("evidence", [])):
            errors.append(f"Source evidence was marked reviewed: {case_id}")
        artifact = record.get("artifact", {})
        raw_path = raw_root / str(artifact.get("source_capture_path", ""))
        if not raw_path.is_file() or sha256_file(raw_path) != artifact.get("source_capture_sha256"):
            errors.append(f"Raw source missing or changed: {case_id}")
        text_hash = hashlib.sha256(str(artifact.get("text", "")).encode("utf-8")).hexdigest()
        if text_hash != artifact.get("text_sha256"):
            errors.append(f"Normalized text hash changed: {case_id}")

    decision = packet.get("decision_gate", {})
    if decision.get("human_confirmation_required") is not True:
        errors.append("Human confirmation gate is not required")
    if any(
        decision.get(field) is not False
        for field in (
            "promote_to_legitimate_label",
            "change_intake_record_state",
            "open_external_scoring",
        )
    ):
        errors.append("A downstream decision gate is open")
    safety = packet.get("safety_contract", {})
    if safety.get("network_operations") != 0 or safety.get("labels_created") != 0:
        errors.append("Safety operation counts are invalid")
    if safety.get("intake_files_modified") is not False or safety.get("raw_files_modified") is not False:
        errors.append("Packet reports source mutation")
    if safety.get("training_allowed") is not False or safety.get("deployment_allowed") is not False:
        errors.append("Training/deployment gate is open")

    result = {
        "analysis_id": registry.get("analysis_id"),
        "status": "VALID" if not errors else "INVALID",
        "record_count": len(records),
        "source_record_count": len(source_records),
        "hard_contradiction_case_count": sum(
            bool(item.get("contradiction_review", {}).get("hard_contradictions"))
            for item in records
        ),
        "human_decision_count": sum(
            item.get("human_decision", {}).get("decision") is not None for item in records
        ),
        "external_evaluation_eligible_count": sum(
            item.get("external_evaluation_eligible") is True for item in records
        ),
        "checked_artifacts": checked,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
