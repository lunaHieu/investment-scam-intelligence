"""Verify the Crimson SEC AI-assisted first-pass registry and safety state."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.normalization.external_references import sha256_file


def load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True, type=Path)
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    errors: list[str] = []
    outputs = {item["role"]: item for item in registry.get("outputs", [])}
    if set(outputs) != {"first_pass_records", "review_workbook"}:
        errors.append("unexpected output roles")

    artifact_results = []
    for role, item in outputs.items():
        path = Path(item["path"])
        if not path.is_file():
            errors.append(f"missing {role}: {path}")
            continue
        actual = sha256_file(path)
        artifact_results.append({"role": role, "expected": item["sha256"], "actual": actual})
        if actual != item["sha256"]:
            errors.append(f"SHA-256 mismatch: {role}")

    records_path = Path(outputs.get("first_pass_records", {}).get("path", ""))
    records = load_jsonl(records_path) if records_path.is_file() else []
    if len(records) != 8 or len({row.get("pilot_id") for row in records}) != 8:
        errors.append("first-pass records must contain eight unique pilot IDs")
    if Counter(row.get("review_status") for row in records) != Counter({"IN_PROGRESS": 8}):
        errors.append("all first-pass records must remain IN_PROGRESS")
    if Counter(row.get("identity_relationship") for row in records) != Counter({"SAME_ENTITY": 8}):
        errors.append("unexpected identity relationship counts")
    if Counter(row.get("evidence_assessment") for row in records) != Counter({"REGISTRATION_RELEVANT": 8}):
        errors.append("unexpected evidence assessment counts")
    if any(
        row.get("training_eligible") != "NO"
        or row.get("label_created") is not False
        or row.get("human_confirmation_required") is not True
        for row in records
    ):
        errors.append("training/label/human-confirmation safety contract violated")

    result = {
        "analysis_id": registry.get("analysis_id"),
        "status": "VALID" if not errors else "INVALID",
        "record_count": len(records),
        "review_status_counts": dict(Counter(row.get("review_status") for row in records)),
        "artifact_results": artifact_results,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
