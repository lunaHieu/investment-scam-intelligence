"""Record one explicit human decision in a new workbook version without mutating intake."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.curation.external_text_reviewer_decisions import record_human_decision
from src.isi.normalization.external_references import sha256_file


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--decision", required=True)
    parser.add_argument("--confidence", required=True, choices=("HIGH", "MEDIUM", "LOW"))
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--reviewed-at", required=True)
    parser.add_argument("--rationale", required=True)
    parser.add_argument("--confirmation-source", required=True)
    parser.add_argument("--unresolved-contradiction", action="append", default=[])
    parser.add_argument("--confirm-all-checks", action="store_true")
    parser.add_argument("--confirm-human-review", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite: {args.output}")
    workbook = load_json(args.input)
    if workbook.get("workbook_id") != "EXTERNAL_TEXT_REVIEWER_DECISION_WORKBOOK_V1":
        raise ValueError("Unexpected reviewer workbook")
    records = workbook.get("records", [])
    matches = [item for item in records if item.get("case_id") == args.case_id]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one case: {args.case_id}")
    completed = record_human_decision(
        matches[0],
        decision=args.decision,
        confidence=args.confidence,
        reviewer=args.reviewer,
        reviewed_at=args.reviewed_at,
        rationale=args.rationale,
        confirmation_source=args.confirmation_source,
        confirm_all_checks=args.confirm_all_checks,
        confirm_human_review=args.confirm_human_review,
        unresolved_contradictions=args.unresolved_contradiction,
    )
    output_records = [completed if item.get("case_id") == args.case_id else item for item in records]
    status_counts = Counter(item.get("human_review", {}).get("status") for item in output_records)
    ready_count = sum(item.get("ready_for_reconciled_intake") is True for item in output_records)
    output = dict(workbook)
    output["created_at"] = datetime.now().astimezone().isoformat()
    output["status"] = (
        "HUMAN_REVIEW_COMPLETE_RECONCILED_INTAKE_NOT_MATERIALIZED"
        if status_counts["COMPLETED"] == len(output_records)
        else "HUMAN_REVIEW_IN_PROGRESS_RECONCILED_INTAKE_NOT_MATERIALIZED"
    )
    output["parent_workbook"] = {
        "path": str(args.input),
        "sha256": sha256_file(args.input),
    }
    output["records"] = output_records
    output["coverage"] = {
        **workbook.get("coverage", {}),
        "pending_review_count": status_counts["PENDING"],
        "completed_review_count": status_counts["COMPLETED"],
        "ready_for_reconciled_intake_count": ready_count,
        "labels_created": 0,
        "external_evaluation_eligible_count": 0,
    }
    output["decision_gate"] = {
        "materialize_reconciled_intake": False,
        "open_external_scoring": False,
        "reason": (
            "Human decisions are only recorded here; a separate validated materialization step "
            "is required and has not run."
        ),
    }
    output["safety_contract"] = {
        **workbook.get("safety_contract", {}),
        "source_intake_files_modified": False,
        "labels_created": 0,
        "model_scoring_operations": 0,
        "model_fit_operations": 0,
        "training_allowed": False,
        "deployment_allowed": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(args.output)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "sha256": sha256_file(args.output),
                "recorded_case": args.case_id,
                "recorded_decision": args.decision,
                "coverage": output["coverage"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
