"""Verify the Crimson IOSCO AI-assisted first-pass registry and safety state."""

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

    live_input = registry.get("inputs", {}).get("live_reference_check", {})
    live_path = ROOT / str(live_input.get("path", ""))
    if not live_path.is_file() or sha256_file(live_path) != live_input.get("sha256"):
        errors.append("live-reference check artifact is missing or has a hash mismatch")
        live = {"records": []}
    else:
        live = json.loads(live_path.read_text(encoding="utf-8"))
    live_records = live.get("records", [])
    if len(live_records) != 41 or len({row.get("url") for row in live_records}) != 41:
        errors.append("live-reference check must cover 41 unique URLs")
    if Counter(row.get("status") for row in live_records) != Counter({"LIVE_CONFIRMED": 23, "LIVE_NOT_CONFIRMED": 18}):
        errors.append("unexpected live-reference URL status counts")

    records_path = Path(outputs.get("first_pass_records", {}).get("path", ""))
    records = load_jsonl(records_path) if records_path.is_file() else []
    if len(records) != 32 or len({row.get("pilot_id") for row in records}) != 32:
        errors.append("first-pass records must contain 32 unique pilot IDs")
    if sum(len(row.get("reference_details", [])) for row in records) != 53:
        errors.append("first-pass records must retain all 53 evidence records")
    if Counter(row.get("review_status") for row in records) != Counter({"IN_PROGRESS": 32}):
        errors.append("all first-pass records must remain IN_PROGRESS")
    if Counter(row.get("identity_relationship") for row in records) != Counter({"SAME_ENTITY": 30, "IMPERSONATION_SUSPECTED": 2}):
        errors.append("unexpected identity relationship counts")
    expected_live = Counter({
        "ALL_URLS_LIVE_CONFIRMED": 16,
        "PARTIAL_URLS_LIVE_CONFIRMED": 9,
        "SNAPSHOT_ONLY_LIVE_NOT_CONFIRMED": 7,
    })
    if Counter(row.get("live_reference_status") for row in records) != expected_live:
        errors.append("unexpected host-level live-reference counts")
    if sum(row.get("second_review_status") == "REQUESTED" for row in records) != 21:
        errors.append("unexpected second-review request count")
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
        "evidence_record_count": sum(len(row.get("reference_details", [])) for row in records),
        "identity_relationship_counts": dict(Counter(row.get("identity_relationship") for row in records)),
        "live_reference_status_counts": dict(Counter(row.get("live_reference_status") for row in records)),
        "artifact_results": artifact_results,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
