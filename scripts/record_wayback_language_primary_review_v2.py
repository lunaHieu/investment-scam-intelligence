"""Validate and freeze the explicit AI primary review for Wayback language V2."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.normalization.external_references import sha256_file


REVIEW_TYPE = "AI_PRIMARY_EVIDENCE_AND_LANGUAGE_REVIEW_NOT_HUMAN"


def validate_response(packet: dict[str, object], response: dict[str, object]) -> list[dict[str, object]]:
    if response.get("review_type") != REVIEW_TYPE:
        raise ValueError("Primary review must be explicitly identified as AI review, not human review")
    if response.get("reviewer") != "OpenAI Codex AI primary reviewer":
        raise ValueError("Unexpected primary reviewer identity")
    items = {str(item["candidate_id"]): item for item in packet.get("items", [])}
    reviews = response.get("reviews", [])
    by_id = {str(item.get("candidate_id")): item for item in reviews}
    if len(reviews) != len(by_id) or set(items) != set(by_id):
        raise ValueError("Primary response must cover each packet candidate exactly once")
    normalized: list[dict[str, object]] = []
    for candidate_id in sorted(items):
        item = items[candidate_id]
        review = by_id[candidate_id]
        contract = item["review_contract"]
        language = review.get("language_decision")
        decision = review.get("evidence_decision")
        confidence = review.get("confidence")
        rationale = str(review.get("rationale", "")).strip()
        checks = [str(value).strip() for value in review.get("evidence_checks", []) if str(value).strip()]
        contradictions = [str(value).strip() for value in review.get("contradictions", []) if str(value).strip()]
        if language not in contract["allowed_language_decisions"]:
            raise ValueError(f"Unsupported language decision: {candidate_id}")
        if decision not in contract["allowed_evidence_decisions"]:
            raise ValueError(f"Unsupported evidence decision: {candidate_id}")
        if confidence not in contract["allowed_confidence"]:
            raise ValueError(f"Unsupported confidence: {candidate_id}")
        if not rationale or not checks:
            raise ValueError(f"Rationale and evidence checks are required: {candidate_id}")
        normalized.append(
            {
                "candidate_id": candidate_id,
                "artifact_text_sha256": item["artifact"]["text_sha256"],
                "capture_sha256": item["artifact"]["capture_sha256"],
                "language_decision": language,
                "evidence_decision": decision,
                "confidence": confidence,
                "rationale": rationale,
                "evidence_checks": checks,
                "contradictions": contradictions,
                "reviewer": response["reviewer"],
                "review_type": REVIEW_TYPE,
                "reviewed_at": response["reviewed_at"],
                "independent_human_review_claimed": False,
            }
        )
    return normalized


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--packet-sha256", required=True)
    parser.add_argument("--response", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {args.output}")
    if sha256_file(args.packet) != args.packet_sha256:
        raise ValueError("Primary-review packet SHA-256 mismatch")
    packet = json.loads(args.packet.read_text(encoding="utf-8"))
    response = json.loads(args.response.read_text(encoding="utf-8"))
    if response.get("packet_sha256") != args.packet_sha256:
        raise ValueError("Response is not bound to this primary-review packet")
    reviews = validate_response(packet, response)
    decision_counts: dict[str, int] = {}
    language_counts: dict[str, int] = {}
    for review in reviews:
        decision = str(review["evidence_decision"])
        language = str(review["language_decision"])
        decision_counts[decision] = decision_counts.get(decision, 0) + 1
        language_counts[language] = language_counts.get(language, 0) + 1
    output = {
        "review_id": "EXTERNAL_TEXT_WAYBACK_LANGUAGE_AI_PRIMARY_REVIEW_V2",
        "status": "AI_PRIMARY_REVIEW_COMPLETE_NOT_HUMAN",
        "inputs": {
            "packet": {"path": str(args.packet), "sha256": args.packet_sha256},
            "response": {"path": str(args.response), "sha256": sha256_file(args.response)},
        },
        "counts": {
            "reviewed": len(reviews),
            "evidence_decisions": decision_counts,
            "language_decisions": language_counts,
        },
        "reviews": reviews,
        "safety_contract": {
            "independent_human_review_claimed": False,
            "model_outputs_consulted": False,
            "warning_or_registry_text_used_as_model_input": False,
            "benchmark_labels_materialized": 0,
            "model_scoring_operations": 0,
            "training_allowed": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": output["status"], "counts": output["counts"], "output": str(args.output), "sha256": sha256_file(args.output)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
