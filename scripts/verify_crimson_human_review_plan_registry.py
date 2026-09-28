"""Verify the prioritized Crimson human-review plan and its closed safety gates."""

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


EXPECTED_PRIORITIES = Counter({
    "P0_IMPERSONATION_SUSPECTED": 2,
    "P1_SECOND_REVIEW_WITH_LIVE_GAP": 11,
    "P2_SECOND_REVIEW_LIVE_CONFIRMED": 8,
    "P3_SINGLE_REVIEW_WITH_LIVE_GAP": 3,
    "P4_SINGLE_REVIEW_OFFICIAL_REFERENCE": 16,
})


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
    artifact_results: list[dict[str, object]] = []
    input_results: list[dict[str, object]] = []
    for role in ("sec_first_pass", "iosco_first_pass"):
        item = registry.get("inputs", {}).get(role, {})
        path = Path(str(item.get("path", "")))
        if not path.is_file():
            errors.append(f"missing input {role}: {path}")
            continue
        actual = sha256_file(path)
        input_results.append({"role": role, "expected": item.get("sha256"), "actual": actual})
        if actual != item.get("sha256"):
            errors.append(f"SHA-256 mismatch: input {role}")
    outputs = {item.get("role"): item for item in registry.get("outputs", [])}
    if set(outputs) != {"human_review_plan", "review_workbook"}:
        errors.append("output roles do not match the human-review plan contract")

    for role, item in outputs.items():
        path = Path(str(item.get("path", "")))
        if not path.is_file():
            errors.append(f"missing output {role}: {path}")
            continue
        actual = sha256_file(path)
        artifact_results.append({"role": role, "expected": item.get("sha256"), "actual": actual})
        if actual != item.get("sha256"):
            errors.append(f"SHA-256 mismatch: {role}")

    plan_path = Path(str(outputs.get("human_review_plan", {}).get("path", "")))
    records = load_jsonl(plan_path) if plan_path.is_file() else []
    if len(records) != 40 or len({row.get("pilot_id") for row in records}) != 40:
        errors.append("human-review plan must contain 40 unique pilot records")
    if sorted(int(row.get("review_order", 0)) for row in records) != list(range(1, 41)):
        errors.append("review order must be a complete 1..40 sequence")
    if any(int(row.get("review_sheet_row", 0)) != int(row.get("pilot_rank", 0)) + 9 for row in records):
        errors.append("review-sheet row mapping is inconsistent with frozen pilot rank")
    expected_order = sorted(
        records,
        key=lambda row: (
            list(EXPECTED_PRIORITIES).index(str(row.get("priority_band"))),
            int(row.get("pilot_rank", 0)),
        ),
    )
    if [row.get("pilot_id") for row in records] != [row.get("pilot_id") for row in expected_order]:
        errors.append("records are not sorted by priority band and pilot rank")
    if Counter(str(row.get("priority_band")) for row in records) != EXPECTED_PRIORITIES:
        errors.append("priority counts do not match the frozen plan")
    if sum(bool(row.get("second_review_required")) for row in records) != 21:
        errors.append("unexpected second-review count")
    if sum(bool(row.get("manual_live_url_followup_required")) for row in records) != 16:
        errors.append("unexpected live-URL follow-up count")
    if any(
        row.get("review_status") != "IN_PROGRESS"
        or row.get("adjudication_status") != "NOT_READY"
        or row.get("training_eligible") != "NO"
        or row.get("label_created") is not False
        or row.get("human_confirmation_required") is not True
        or row.get("do_not_open_crimson_host") is not True
        for row in records
    ):
        errors.append("human-review safety state is not closed")

    safety = registry.get("safety_contract", {})
    if safety.get("network_operations") != 0 or safety.get("labels_created") != 0:
        errors.append("safety counts must remain zero")
    if safety.get("training_allowed") is not False or safety.get("domain_access_allowed") is not False:
        errors.append("training/domain-access gates must remain closed")
    if safety.get("automatic_adjudication_allowed") is not False or safety.get("human_confirmation_required") is not True:
        errors.append("human adjudication gate is invalid")

    result = {
        "analysis_id": registry.get("analysis_id"),
        "status": "VALID" if not errors else "INVALID",
        "record_count": len(records),
        "priority_counts": dict(Counter(str(row.get("priority_band")) for row in records)),
        "second_review_required_count": sum(bool(row.get("second_review_required")) for row in records),
        "manual_live_url_followup_count": sum(bool(row.get("manual_live_url_followup_required")) for row in records),
        "input_results": input_results,
        "artifact_results": artifact_results,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
