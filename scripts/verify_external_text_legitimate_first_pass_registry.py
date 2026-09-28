"""Verify the frozen AI-assisted first pass and its no-label decision."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from validate_external_text_intake import sha256_file


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True, type=Path)
    args = parser.parse_args()
    registry = load_json(args.registry)
    root = args.registry.resolve().parents[2]
    errors: list[str] = []
    artifact_results = []
    if registry.get("analysis_id") != "EXTERNAL_TEXT_LEGITIMATE_AI_ASSISTED_FIRST_PASS_V1":
        errors.append("Unexpected analysis ID")
    if registry.get("status") != "TWO_AI_RECOMMENDATIONS_HUMAN_CONFIRMATION_REQUIRED_NOT_LABELED":
        errors.append("Unexpected analysis status")

    for item in [*registry.get("inputs", []), *registry.get("outputs", [])]:
        path = Path(str(item.get("path", "")))
        if not path.is_absolute():
            path = root / path
        actual = sha256_file(path) if path.is_file() else None
        artifact_results.append({"role": item.get("role"), "path": str(path), "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"Artifact missing or changed: {item.get('role')}")

    outputs = {item.get("role"): item for item in registry.get("outputs", [])}
    first_pass_path = Path(str(outputs.get("first_pass_records", {}).get("path", "")))
    first_pass = load_json(first_pass_path) if first_pass_path.is_file() else {}
    records = first_pass.get("records", [])
    if len(records) != 2:
        errors.append("First pass must contain exactly two records")
    expected_state = {
        "ground_truth_status": "UNCERTAIN",
        "label_confidence": "LOW",
        "review_status": "IN_REVIEW",
    }
    for record in records:
        state = record.get("current_state", {})
        suggestion = record.get("ai_first_pass", {})
        if state != expected_state:
            errors.append(f"Current state changed: {record.get('case_id')}")
        if suggestion.get("counts_as_label") is not False or suggestion.get("counts_as_human_review") is not False:
            errors.append(f"Suggestion was promoted: {record.get('case_id')}")
        if suggestion.get("recommended_outcome_for_human_review") != "LEGITIMATE":
            errors.append(f"Unexpected bounded recommendation: {record.get('case_id')}")

    coverage = registry.get("coverage", {})
    if coverage.get("human_confirmed_record_count") != 0:
        errors.append("Human confirmation count must remain zero")
    if coverage.get("external_evaluation_eligible_count") != 0 or coverage.get("labels_created") != 0:
        errors.append("Registry improperly reports eligible/labeled records")
    decision = registry.get("decision", {})
    if any(
        decision.get(field) is not False
        for field in (
            "promote_to_legitimate_label",
            "change_intake_record_state",
            "open_external_scoring",
        )
    ):
        errors.append("Decision gate was opened")
    safety = registry.get("safety_contract", {})
    if safety.get("network_operations") != 0 or safety.get("labels_created") != 0:
        errors.append("First pass must remain offline and unlabeled")
    if safety.get("training_allowed") is not False or safety.get("domain_access_allowed") is not False:
        errors.append("Training/domain gate was opened")

    result = {
        "analysis_id": registry.get("analysis_id"),
        "status": "VALID" if not errors else "INVALID",
        "record_count": len(records),
        "human_confirmed_record_count": coverage.get("human_confirmed_record_count"),
        "external_evaluation_eligible_count": coverage.get("external_evaluation_eligible_count"),
        "artifact_results": artifact_results,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
