"""Record an explicitly confirmed first human review for one Crimson pilot case."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BRIEF = ROOT / "reports" / "crimson_external_reference_review_pilot_v1" / "PILOT_CRIMSON_REF_018_review_brief_v1.json"
DEFAULT_OUTPUT = Path(r"D:\nckh 2026-2027\ISI_Data\curated\crimson_external_reference_review_pilot_v1\human_review_decisions_v1.jsonl")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_decision(
    brief: dict[str, Any],
    reviewer: str,
    reviewed_date: str,
    confirmation_source: str,
    source_brief_sha256: str,
) -> dict[str, Any]:
    recommendation = brief.get("recommended_human_decision", {})
    workflow = brief.get("workflow_state", {})
    if workflow.get("human_confirmation_required") is not True:
        raise ValueError("Review brief does not require human confirmation")
    if not reviewer.strip() or not confirmation_source.strip():
        raise ValueError("Reviewer and confirmation source are required")
    if recommendation.get("second_review_required") != "YES":
        raise ValueError("This decision recorder expects the first review of a second-review case")
    return {
        "decision_id": f"{brief['pilot_id']}_HUMAN_FIRST_REVIEW_V1",
        "pilot_id": str(brief["pilot_id"]),
        "pilot_rank": int(brief["pilot_rank"]),
        "crimson_host": str(brief["crimson_host"]),
        "decision_stage": "HUMAN_FIRST_REVIEW",
        "review_status": "COMPLETED",
        "official_reference_checked": str(recommendation["official_reference_checked"]),
        "identity_relationship": str(recommendation["identity_relationship"]),
        "evidence_assessment": str(recommendation["evidence_assessment"]),
        "reviewer": reviewer.strip(),
        "reviewed_date": reviewed_date,
        "review_notes": (
            f"Human reviewer confirmed the official regulator evidence summarized in {brief['brief_id']}. "
            f"Decision: {recommendation['identity_relationship']} + {recommendation['evidence_assessment']}. "
            "A separate second human review is still required."
        ),
        "second_review_status": "REQUESTED",
        "second_reviewer": "",
        "second_review_required": True,
        "confirmation_source": confirmation_source.strip(),
        "source_brief_id": str(brief["brief_id"]),
        "source_brief_sha256": source_brief_sha256,
        "live_reference_status": str(brief["current_live_reference_status"]),
        "adjudication_status": "SECOND_REVIEW_REQUIRED",
        "human_confirmation_recorded": True,
        "training_eligible": "NO",
        "label_created": False,
    }


def append_jsonl(path: Path, decision: dict[str, Any]) -> None:
    existing: list[dict[str, Any]] = []
    if path.exists():
        existing = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if any(row.get("pilot_id") == decision["pilot_id"] and row.get("decision_stage") == decision["decision_stage"] for row in existing):
        raise ValueError(f"A first human review already exists for {decision['pilot_id']}")
    payload = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in [*existing, decision])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", type=Path, default=DEFAULT_BRIEF)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--reviewed-date", required=True)
    parser.add_argument("--confirmation-source", required=True)
    parser.add_argument("--confirm-recommendation", action="store_true")
    args = parser.parse_args()
    if not args.confirm_recommendation:
        raise ValueError("Explicit --confirm-recommendation is required")
    brief = json.loads(args.brief.read_text(encoding="utf-8"))
    decision = build_decision(
        brief,
        args.reviewer,
        args.reviewed_date,
        args.confirmation_source,
        sha256_file(args.brief),
    )
    append_jsonl(args.output, decision)
    records = [json.loads(line) for line in args.output.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(json.dumps({
        "output": str(args.output),
        "record_count": len(records),
        "sha256": sha256_file(args.output),
        "recorded_decision": decision,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
