"""Independently verify the frozen 21-case external pilot as a module.

This V2 verifier leaves the hash-pinned historical V1 implementation unchanged.
It performs only offline reads and never scores a model or changes labels/raw data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.validate_external_text_intake import sha256_file, validate_batch


EXPECTED_ANALYSIS_ID = "EXTERNAL_TEXT_RECONCILED_PILOT_V1"
EXPECTED_STATUS = "RECONCILED_21_OF_21_ELIGIBLE_REPORTING_GATE_OPEN"
EXPECTED_OUTPUT_ROLES = {
    "reconciled_intake_json",
    "reconciled_intake_markdown",
    "validation_report",
}


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def resolve(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def verify(registry_path: Path, *, repo_root: Path | None = None) -> dict[str, Any]:
    registry = load_object(registry_path)
    root = repo_root.resolve() if repo_root is not None else registry_path.resolve().parents[2]
    errors: list[str] = []
    checked: list[dict[str, Any]] = []

    if registry.get("analysis_id") != EXPECTED_ANALYSIS_ID:
        errors.append("Unexpected analysis ID")
    if registry.get("status") != EXPECTED_STATUS:
        errors.append("Unexpected status")

    raw_inputs = registry.get("inputs")
    implementation = registry.get("implementation")
    raw_outputs = registry.get("outputs")
    if not isinstance(raw_inputs, dict):
        errors.append("inputs must be an object")
        raw_inputs = {}
    if not isinstance(implementation, list):
        errors.append("implementation must be a list")
        implementation = []
    if not isinstance(raw_outputs, list):
        errors.append("outputs must be a list")
        raw_outputs = []

    entries = list(implementation) + list(raw_inputs.values()) + list(raw_outputs)
    for item in entries:
        if not isinstance(item, dict):
            errors.append("Registry artifact entry must be an object")
            continue
        path = resolve(root, item.get("path"))
        actual = sha256_file(path) if path.is_file() else None
        checked.append({"role": item.get("role"), "path": str(path), "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"Artifact missing or changed: {path}")

    outputs = {
        item.get("role"): item
        for item in raw_outputs
        if isinstance(item, dict) and isinstance(item.get("role"), str)
    }
    if set(outputs) != EXPECTED_OUTPUT_ROLES:
        errors.append("Unexpected output roles")

    intake_path = resolve(root, outputs.get("reconciled_intake_json", {}).get("path", ""))
    validation_path = resolve(root, outputs.get("validation_report", {}).get("path", ""))
    raw_root = Path(str(registry.get("raw_root", "")))
    labels: Counter[str] = Counter()
    eligible_count = 0
    if intake_path.is_file() and validation_path.is_file():
        intake = load_object(intake_path)
        validation = load_object(validation_path)
        fresh_errors, fresh_report = validate_batch(intake, raw_root)
        records = intake.get("records")
        if not isinstance(records, list):
            errors.append("Reconciled intake records must be a list")
            records = []
        labels = Counter(
            str(item.get("ground_truth_status"))
            for item in records
            if isinstance(item, dict)
        )
        if labels != Counter({"LEGITIMATE": 11, "CONFIRMED": 10}):
            errors.append(f"Unexpected labels: {dict(labels)}")
        eligible_count = int(fresh_report.get("eligible_count", 0))
        if fresh_errors or fresh_report.get("reporting_allowed") is not True:
            errors.append(f"Fresh validation failed: {fresh_errors}")
        if (
            validation.get("input_sha256") != sha256_file(intake_path)
            or validation.get("eligible_count") != 21
            or validation.get("reporting_allowed") is not True
        ):
            errors.append("Frozen validation report does not bind an open 21-case gate")
        for item in records:
            if not isinstance(item, dict):
                errors.append("Reconciled record must be an object")
                continue
            provenance = item.get("review_provenance")
            if not isinstance(provenance, dict):
                provenance = {}
            if (
                item.get("label_confidence") != "HIGH"
                or item.get("review_status") != "RECONCILED"
                or item.get("external_evaluation_eligible") is not True
                or provenance.get("independent_human_evidence_rereview") is not False
            ):
                errors.append(f"Record contract mismatch: {item.get('case_id')}")
    else:
        errors.append("Reconciled intake or validation report is unavailable")

    review = registry.get("review_provenance")
    if not isinstance(review, dict):
        errors.append("Registry review provenance missing")
        review = {}
    if review.get("ai_manual_review_completed") is not True:
        errors.append("AI review completion is not preserved")
    if review.get("project_owner_adopted_progression") is not True:
        errors.append("Owner adoption is not preserved")
    if review.get("independent_human_evidence_rereview") is not False:
        errors.append("Independent human rereview must remain false")
    if review.get("double_reviewed_gold_benchmark") is not False:
        errors.append("Pilot must not be represented as double-reviewed gold")

    safety = registry.get("safety_contract")
    if not isinstance(safety, dict):
        errors.append("Safety contract missing")
        safety = {}
    for key in ("model_scoring_operations", "model_fit_operations"):
        if safety.get(key) != 0:
            errors.append(f"Unexpected model operation: {key}")
    if safety.get("training_allowed") is not False or safety.get("deployment_allowed") is not False:
        errors.append("Training or deployment gate opened")

    return {
        "valid": not errors,
        "errors": errors,
        "analysis_id": registry.get("analysis_id"),
        "record_count": sum(labels.values()),
        "confirmed_count": labels.get("CONFIRMED", 0),
        "legitimate_count": labels.get("LEGITIMATE", 0),
        "eligible_count": eligible_count,
        "independent_human_evidence_rereview": review.get("independent_human_evidence_rereview"),
        "double_reviewed_gold_benchmark": review.get("double_reviewed_gold_benchmark"),
        "checked": checked,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.registry)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
