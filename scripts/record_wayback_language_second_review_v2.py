"""Validate and freeze an independent blinded AI second review for Wayback V2."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.normalization.external_references import sha256_file


REVIEW_TYPE = "INDEPENDENT_BLINDED_AI_SECOND_REVIEW_NOT_HUMAN"


def validate_reviews(packet: dict[str, object], response: dict[str, object]) -> list[dict[str, object]]:
    if response.get("review_type") != REVIEW_TYPE:
        raise ValueError("Second review must be explicitly identified as independent blinded AI review")
    if response.get("reviewer") != "OpenAI Codex independent blinded AI reviewer":
        raise ValueError("Unexpected independent reviewer identity")
    packet_items = {str(item["blind_review_id"]): item for item in packet.get("items", [])}
    reviews = response.get("reviews", [])
    review_items = {str(item.get("blind_review_id")): item for item in reviews}
    if len(reviews) != len(review_items) or set(packet_items) != set(review_items):
        raise ValueError("Second review must cover each blind ID exactly once")
    prohibited = {"candidate_id", "source_case_id", "reference_branch", "first_review", "model_prediction", "score_label_1"}
    normalized: list[dict[str, object]] = []
    for review_id in sorted(packet_items):
        review = review_items[review_id]
        if prohibited.intersection(str(key).casefold() for key in review):
            raise ValueError(f"Second review leaks a prohibited field: {review_id}")
        contract = packet_items[review_id]["review_contract"]
        decision = review.get("decision")
        confidence = review.get("confidence")
        rationale = str(review.get("rationale", "")).strip()
        checks = [str(value).strip() for value in review.get("evidence_checks", []) if str(value).strip()]
        contradictions = [str(value).strip() for value in review.get("contradictions", []) if str(value).strip()]
        if decision not in contract["allowed_decisions"]:
            raise ValueError(f"Unsupported decision: {review_id}")
        if confidence not in contract["allowed_confidence"]:
            raise ValueError(f"Unsupported confidence: {review_id}")
        if not rationale or not checks:
            raise ValueError(f"Rationale and evidence checks are required: {review_id}")
        normalized.append(
            {
                "blind_review_id": review_id,
                "decision": decision,
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
        raise ValueError("Blind packet SHA-256 mismatch")
    packet = json.loads(args.packet.read_text(encoding="utf-8"))
    response = json.loads(args.response.read_text(encoding="utf-8"))
    if response.get("packet_sha256") != args.packet_sha256:
        raise ValueError("Second-review response is not bound to this packet")
    reviews = validate_reviews(packet, response)
    decision_counts: dict[str, int] = {}
    confidence_counts: dict[str, int] = {}
    for review in reviews:
        decision = str(review["decision"])
        confidence = str(review["confidence"])
        decision_counts[decision] = decision_counts.get(decision, 0) + 1
        confidence_counts[confidence] = confidence_counts.get(confidence, 0) + 1
    output = {
        "review_id": "EXTERNAL_TEXT_WAYBACK_LANGUAGE_INDEPENDENT_SECOND_REVIEW_V2",
        "status": "INDEPENDENT_BLINDED_AI_SECOND_REVIEW_COMPLETE_NOT_HUMAN",
        "inputs": {
            "packet": {"path": str(args.packet), "sha256": args.packet_sha256},
            "response": {"path": str(args.response), "sha256": sha256_file(args.response)},
        },
        "counts": {
            "reviewed": len(reviews),
            "decisions": decision_counts,
            "confidence": confidence_counts,
        },
        "reviews": reviews,
        "safety_contract": {
            "mapping_exposed_to_reviewer": False,
            "first_review_exposed_to_reviewer": False,
            "model_outputs_exposed_to_reviewer": False,
            "independent_human_review_claimed": False,
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
