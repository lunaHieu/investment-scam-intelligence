"""Verify explicitly confirmed Crimson human-review decisions and closed gates."""

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
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True, type=Path)
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    errors: list[str] = []
    results: list[dict[str, object]] = []

    brief = registry.get("inputs", {}).get("review_brief", {})
    brief_path = ROOT / str(brief.get("path", ""))
    if not brief_path.is_file():
        errors.append(f"missing review brief: {brief_path}")
    else:
        actual = sha256_file(brief_path)
        results.append({"role": "review_brief", "expected": brief.get("sha256"), "actual": actual})
        if actual != brief.get("sha256"):
            errors.append("review brief SHA-256 mismatch")

    outputs = {item.get("role"): item for item in registry.get("outputs", [])}
    if set(outputs) != {"human_review_decisions", "review_workbook"}:
        errors.append("output roles do not match the human-decision contract")
    for role, item in outputs.items():
        path = Path(str(item.get("path", "")))
        if not path.is_file():
            errors.append(f"missing output {role}: {path}")
            continue
        actual = sha256_file(path)
        results.append({"role": role, "expected": item.get("sha256"), "actual": actual})
        if actual != item.get("sha256"):
            errors.append(f"SHA-256 mismatch: {role}")

    decision_path = Path(str(outputs.get("human_review_decisions", {}).get("path", "")))
    records = load_jsonl(decision_path) if decision_path.is_file() else []
    if len(records) != 1:
        errors.append("expected exactly one recorded first human review")
    if len({row.get("decision_id") for row in records}) != len(records):
        errors.append("decision IDs must be unique")
    if Counter(str(row.get("review_status")) for row in records) != Counter({"COMPLETED": 1}):
        errors.append("unexpected review status counts")
    if any(
        row.get("decision_stage") != "HUMAN_FIRST_REVIEW"
        or row.get("official_reference_checked") != "YES"
        or row.get("identity_relationship") != "IMPERSONATION_SUSPECTED"
        or row.get("evidence_assessment") != "WARNING_RELEVANT"
        or row.get("second_review_status") != "REQUESTED"
        or row.get("adjudication_status") != "SECOND_REVIEW_REQUIRED"
        or row.get("training_eligible") != "NO"
        or row.get("label_created") is not False
        or row.get("human_confirmation_recorded") is not True
        for row in records
    ):
        errors.append("recorded decision violates the confirmed first-review contract")

    safety = registry.get("safety_contract", {})
    if safety.get("labels_created") != 0 or safety.get("training_allowed") is not False:
        errors.append("label/training gates must remain closed")
    if safety.get("automatic_second_review_allowed") is not False or safety.get("second_human_review_required") is not True:
        errors.append("second-human-review gate is invalid")

    result = {
        "analysis_id": registry.get("analysis_id"),
        "status": "VALID" if not errors else "INVALID",
        "decision_count": len(records),
        "review_status_counts": dict(Counter(str(row.get("review_status")) for row in records)),
        "adjudication_status_counts": dict(Counter(str(row.get("adjudication_status")) for row in records)),
        "artifact_results": results,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
