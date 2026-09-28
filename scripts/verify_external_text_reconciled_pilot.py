"""Verify the frozen 21-case reconciled external-text pilot."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from validate_external_text_intake import sha256_file, validate_batch


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
    checked = []
    if registry.get("analysis_id") != "EXTERNAL_TEXT_RECONCILED_PILOT_V1":
        errors.append("Unexpected analysis ID")
    if registry.get("status") != "RECONCILED_21_OF_21_ELIGIBLE_REPORTING_GATE_OPEN":
        errors.append("Unexpected status")
    entries = list(registry.get("implementation", [])) + list(registry.get("inputs", {}).values())
    outputs = {item.get("role"): item for item in registry.get("outputs", [])}
    entries.extend(outputs.values())
    for item in entries:
        path = resolve(root, item.get("path"))
        actual = sha256_file(path) if path.is_file() else None
        checked.append({"path": str(path), "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"Artifact missing or changed: {path}")
    expected_roles = {"reconciled_intake_json", "reconciled_intake_markdown", "validation_report"}
    if set(outputs) != expected_roles:
        errors.append("Unexpected output roles")
    intake_path = resolve(root, outputs.get("reconciled_intake_json", {}).get("path", ""))
    validation_path = resolve(root, outputs.get("validation_report", {}).get("path", ""))
    raw_root = Path(str(registry.get("raw_root", "")))
    if intake_path.is_file() and validation_path.is_file():
        intake = load_json(intake_path)
        validation = load_json(validation_path)
        fresh_errors, fresh_report = validate_batch(intake, raw_root)
        records = intake.get("records", [])
        labels = Counter(item.get("ground_truth_status") for item in records)
        if labels != Counter({"LEGITIMATE": 11, "CONFIRMED": 10}):
            errors.append(f"Unexpected labels: {dict(labels)}")
        if fresh_errors or fresh_report.get("reporting_allowed") is not True:
            errors.append(f"Fresh validation failed: {fresh_errors}")
        if (
            validation.get("input_sha256") != sha256_file(intake_path)
            or validation.get("eligible_count") != 21
            or validation.get("reporting_allowed") is not True
        ):
            errors.append("Frozen validation report does not bind an open 21-case gate")
        for item in records:
            provenance = item.get("review_provenance", {})
            if (
                item.get("label_confidence") != "HIGH"
                or item.get("review_status") != "RECONCILED"
                or item.get("external_evaluation_eligible") is not True
                or provenance.get("independent_human_evidence_rereview") is not False
            ):
                errors.append(f"Record contract mismatch: {item.get('case_id')}")
    else:
        errors.append("Reconciled intake or validation report is unavailable")
    print(json.dumps({"valid": not errors, "errors": errors, "checked": checked}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

