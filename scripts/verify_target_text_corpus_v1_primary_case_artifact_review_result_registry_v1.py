"""Verify the registered primary case-and-artifact review result and closed gates."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object: {path}")
    return value


def resolve(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def verify(registry_path: Path) -> list[str]:
    registry = load(registry_path)
    root = registry_path.resolve().parents[2]
    errors: list[str] = []
    for section in ("inputs", "implementation", "outputs"):
        for item in registry.get(section, []):
            path = resolve(root, item["path"])
            if not path.is_file():
                errors.append(f"Missing {section} artifact: {item['role']}")
            elif sha(path) != item["sha256"]:
                errors.append(f"Hash mismatch for {section} artifact: {item['role']}")
    findings = registry.get("findings", {})
    expected = {
        "reviewed_records": 22,
        "primary_confirmed_recommendations": 4,
        "primary_legitimate_recommendations": 11,
        "primary_uncertain_recommendations": 7,
        "labels_created": 0,
        "training_eligible_records": 0,
    }
    if findings != expected:
        errors.append(f"Unexpected findings: {findings}")
    decision = registry.get("decision", {})
    required = {
        "primary_review_complete": True,
        "blind_independent_second_review_allowed": True,
        "ground_truth_labeling_completed": False,
        "owner_acceptance_still_required": True,
        "model_scoring_allowed": False,
        "training_allowed": False,
    }
    for key, value in required.items():
        if decision.get(key) is not value:
            errors.append(f"Unexpected decision gate {key}: {decision.get(key)}")
    safety = registry.get("safety_contract", {})
    for key in ("labels_created", "labels_changed", "model_fit_operations", "model_scoring_operations", "validation_or_test_openings"):
        if safety.get(key) != 0:
            errors.append(f"Safety counter is not zero: {key}")
    if safety.get("training_allowed") is not False:
        errors.append("Training gate unexpectedly open")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    args = parser.parse_args()
    errors = verify(args.registry)
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
