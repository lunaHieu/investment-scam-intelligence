"""Verify the blank external-text reviewer workbook and all closed gates."""

from __future__ import annotations

import argparse
import json
from collections import Counter
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

    if registry.get("analysis_id") != "EXTERNAL_TEXT_REVIEWER_DECISION_WORKBOOK_V1":
        errors.append("Unexpected registry analysis ID")
    if registry.get("status") != "TWENTY_ONE_PENDING_HUMAN_REVIEWS_ZERO_DECISIONS_ZERO_ELIGIBLE":
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
    if set(outputs) != {"reviewer_workbook_json", "reviewer_workbook_markdown"}:
        errors.append("Unexpected output roles")
    for role, item in outputs.items():
        path = resolve_path(root, item.get("path"))
        actual = sha256_file(path) if path.is_file() else None
        checked.append({"role": role, "path": str(path), "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"Output missing or changed: {role}")

    workbook_path = resolve_path(
        root, outputs.get("reviewer_workbook_json", {}).get("path", "")
    )
    workbook = load_json(workbook_path) if workbook_path.is_file() else {}
    if workbook.get("workbook_id") != "EXTERNAL_TEXT_REVIEWER_DECISION_WORKBOOK_V1":
        errors.append("Unexpected workbook ID")
    if workbook.get("status") != "TWENTY_ONE_PENDING_HUMAN_REVIEWS_ZERO_DECISIONS_ZERO_ELIGIBLE":
        errors.append("Unexpected workbook status")

    records = workbook.get("records", [])
    if len(records) != 21:
        errors.append("Workbook must contain exactly 21 records")
    case_ids = [str(item.get("case_id")) for item in records]
    if len(case_ids) != len(set(case_ids)):
        errors.append("Workbook contains duplicate case IDs")
    branch_counts = Counter(str(item.get("branch")) for item in records)
    if branch_counts != Counter({"CONFIRMED": 10, "LEGITIMATE": 11}):
        errors.append("Workbook branch counts are invalid")
    priority_counts = Counter(str(item.get("review_priority")) for item in records)
    expected_priority_counts = Counter(
        {
            "P1_CONFIRMED_LOCAL_WARNING_IDENTITY_VISIBLE": 2,
            "P2_CONFIRMED_MANUAL_WARNING_FOLLOW_UP": 8,
            "P3_LEGITIMATE_HIGH_ALIGNMENT": 6,
            "P4_LEGITIMATE_EXTRA_IDENTITY_REVIEW": 5,
        }
    )
    if priority_counts != expected_priority_counts:
        errors.append("Workbook priority counts are invalid")

    for record in records:
        case_id = record.get("case_id")
        review = record.get("human_review", {})
        if review.get("status") != "PENDING":
            errors.append(f"Review is not pending: {case_id}")
        for field in (
            "final_decision",
            "label_confidence",
            "reviewer",
            "reviewed_at",
            "rationale",
            "confirmation_source",
        ):
            if review.get(field) is not None:
                errors.append(f"Human field was pre-filled for {case_id}: {field}")
        if review.get("unresolved_contradictions") != []:
            errors.append(f"Pending form has pre-filled contradictions: {case_id}")
        if review.get("human_confirmation_recorded") is not False:
            errors.append(f"Human confirmation was pre-recorded: {case_id}")
        confirmations = record.get("evidence_confirmations", {})
        required = record.get("review_contract", {}).get("required_checks", [])
        if set(confirmations) != set(required) or any(
            value is not None for value in confirmations.values()
        ):
            errors.append(f"Evidence checklist is not blank and complete: {case_id}")
        if record.get("automated_context", {}).get("recommendation_is_ground_truth") is not False:
            errors.append(f"Automated recommendation became ground truth: {case_id}")
        if any(
            record.get(field) is not False
            for field in (
                "ready_for_reconciled_intake",
                "source_intake_changed",
                "label_created",
                "external_evaluation_eligible",
            )
        ):
            errors.append(f"A pending form opened a downstream gate: {case_id}")

    expected_coverage = {
        "record_count": 21,
        "confirmed_branch_count": 10,
        "legitimate_branch_count": 11,
        "priority_counts": dict(sorted(expected_priority_counts.items())),
        "pending_review_count": 21,
        "completed_review_count": 0,
        "ready_for_reconciled_intake_count": 0,
        "labels_created": 0,
        "external_evaluation_eligible_count": 0,
    }
    if workbook.get("coverage") != expected_coverage:
        errors.append("Workbook coverage differs from the frozen contract")

    for role in (
        "confirmed_registry",
        "confirmed_packet",
        "legitimate_registry",
        "legitimate_packet",
    ):
        item = workbook.get("inputs", {}).get(role, {})
        path = resolve_path(root, item.get("path"))
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            errors.append(f"Workbook input missing or changed: {role}")
    decision = workbook.get("decision_gate", {})
    if decision.get("materialize_reconciled_intake") is not False:
        errors.append("Reconciled-intake materialization gate is open")
    if decision.get("open_external_scoring") is not False:
        errors.append("External scoring gate is open")
    safety = workbook.get("safety_contract", {})
    if safety.get("network_operations") != 0 or safety.get("labels_created") != 0:
        errors.append("Workbook safety counts are invalid")
    if safety.get("source_intake_files_modified") is not False:
        errors.append("Workbook reports source intake mutation")
    if safety.get("training_allowed") is not False or safety.get("deployment_allowed") is not False:
        errors.append("Training/deployment gate is open")

    result = {
        "workbook_id": workbook.get("workbook_id"),
        "status": "VALID" if not errors else "INVALID",
        "record_count": len(records),
        "branch_counts": dict(sorted(branch_counts.items())),
        "priority_counts": dict(sorted(priority_counts.items())),
        "pending_review_count": sum(
            item.get("human_review", {}).get("status") == "PENDING" for item in records
        ),
        "completed_review_count": sum(
            item.get("human_review", {}).get("status") == "COMPLETED" for item in records
        ),
        "labels_created": sum(item.get("label_created") is True for item in records),
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
