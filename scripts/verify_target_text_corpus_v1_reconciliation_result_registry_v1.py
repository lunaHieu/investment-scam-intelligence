"""Verify the registered target-text reconciliation result."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(path: Path) -> list[str]:
    registry = json.loads(path.read_text(encoding="utf-8"))
    root = path.resolve().parents[2]
    errors: list[str] = []
    for section in ("inputs", "implementation", "outputs"):
        for item in registry[section]:
            item_path = Path(item["path"])
            item_path = item_path if item_path.is_absolute() else root / item_path
            if not item_path.is_file() or sha(item_path) != item["sha256"]:
                errors.append(f"Missing or changed {section} artifact: {item['role']}")
    findings = registry["findings"]
    if (findings["reviewed_records"], findings["agreements"], findings["disagreements_resolved"]) != (22, 20, 2):
        errors.append("Unexpected reconciliation coverage")
    if findings["duplicate_registration_composite_keys"] != 0:
        errors.append("Registration-key collision remains")
    if (findings["labels_created"], findings["training_eligible_records"]) != (0, 0):
        errors.append("Labels or training eligibility created")
    decision = registry["decision"]
    if decision.get("owner_acceptance_required") is not True or decision.get("ground_truth_labeling_completed") is not False or decision.get("training_allowed") is not False:
        errors.append("Downstream gate state is invalid")
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
