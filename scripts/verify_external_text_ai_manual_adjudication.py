"""Verify the frozen external-text AI manual-adjudication artifact."""

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


def resolve(root: Path, value: object) -> Path:
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
    if registry.get("analysis_id") != "EXTERNAL_TEXT_AI_MANUAL_ADJUDICATION_V1":
        errors.append("Unexpected registry analysis ID")
    expected_status = "TWENTY_ONE_AI_REVIEWS_COMPLETE_HUMAN_CONFIRMATION_PENDING_ZERO_ELIGIBLE"
    if registry.get("status") != expected_status:
        errors.append("Unexpected registry status")

    entries = list(registry.get("implementation", [])) + list(registry.get("inputs", {}).values())
    for item in entries:
        path = resolve(root, item.get("path"))
        actual = sha256_file(path) if path.is_file() else None
        checked.append({"path": str(path), "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"Artifact missing or changed: {path}")
    outputs = {item.get("role"): item for item in registry.get("outputs", [])}
    if set(outputs) != {"ai_adjudication_json", "ai_adjudication_markdown"}:
        errors.append("Unexpected output roles")
    for item in outputs.values():
        path = resolve(root, item.get("path"))
        actual = sha256_file(path) if path.is_file() else None
        checked.append({"path": str(path), "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"Output missing or changed: {path}")

    report_path = resolve(root, outputs.get("ai_adjudication_json", {}).get("path", ""))
    if report_path.is_file():
        report = load_json(report_path)
        records = report.get("records", [])
        if report.get("analysis_id") != registry.get("analysis_id"):
            errors.append("Report and registry analysis IDs differ")
        if report.get("status") != expected_status:
            errors.append("Unexpected report status")
        if len(records) != 21 or len({item.get("case_id") for item in records}) != 21:
            errors.append("Expected 21 unique records")
        decisions = Counter(item.get("ai_review", {}).get("recommended_decision") for item in records)
        if decisions != Counter({"LEGITIMATE": 11, "CONFIRMED": 10}):
            errors.append(f"Unexpected recommendation counts: {dict(decisions)}")
        for item in records:
            ai = item.get("ai_review", {})
            human = item.get("human_review", {})
            if ai.get("status") != "COMPLETED" or ai.get("reviewer_type") != "AI_AGENT":
                errors.append(f"Incomplete AI review: {item.get('case_id')}")
            if ai.get("recommended_confidence") != "HIGH":
                errors.append(f"Unexpected confidence: {item.get('case_id')}")
            if ai.get("ready_for_human_adoption") is not True:
                errors.append(f"Not ready for human adoption: {item.get('case_id')}")
            if ai.get("recommendation_is_ground_truth") is not False:
                errors.append(f"AI recommendation promoted to ground truth: {item.get('case_id')}")
            if human.get("status") != "PENDING" or human.get("human_confirmation_recorded") is not False:
                errors.append(f"Human gate unexpectedly open: {item.get('case_id')}")
            for flag in (
                "ready_for_reconciled_intake",
                "source_intake_changed",
                "label_created",
                "external_evaluation_eligible",
            ):
                if item.get(flag) is not False:
                    errors.append(f"Closed gate changed ({flag}): {item.get('case_id')}")
    else:
        errors.append("AI adjudication JSON is unavailable")

    result = {
        "registry": str(args.registry),
        "valid": not errors,
        "errors": errors,
        "checked_artifacts": checked,
    }
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

