"""Validate and freeze an independent blinded AI second-review response."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for value in (ROOT, SCRIPTS):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

from validate_external_text_intake import sha256_file


REVIEW_TYPE = "INDEPENDENT_BLINDED_AI_SECOND_REVIEW_NOT_HUMAN"


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def validate_reviews(packet: dict[str, object], response: dict[str, object]) -> list[dict]:
    if response.get("review_type") != REVIEW_TYPE:
        raise ValueError("Second review must be explicitly recorded as independent blinded AI, not human")
    if response.get("reviewer") != "OpenAI Codex independent blinded AI reviewer":
        raise ValueError("Unexpected independent reviewer identity")
    packet_items = {item["blind_review_id"]: item for item in packet.get("items", [])}
    reviews = response.get("reviews", [])
    review_items = {item.get("blind_review_id"): item for item in reviews}
    if len(reviews) != len(review_items) or set(packet_items) != set(review_items):
        raise ValueError("Second review must cover each blind ID exactly once")
    prohibited = {"candidate_id", "source_case_id", "reference_status", "model_prediction", "score_label_1"}
    normalized = []
    for review_id in sorted(packet_items):
        review = review_items[review_id]
        if prohibited.intersection(review):
            raise ValueError(f"Second review leaks a prohibited field: {review_id}")
        contract = packet_items[review_id]["review_contract"]
        decision = review.get("decision")
        confidence = review.get("confidence")
        rationale = str(review.get("rationale", "")).strip()
        checks = [str(item).strip() for item in review.get("evidence_checks", []) if str(item).strip()]
        contradictions = [str(item).strip() for item in review.get("contradictions", []) if str(item).strip()]
        if decision not in contract["allowed_decisions"]:
            raise ValueError(f"Unsupported decision: {review_id}")
        if confidence not in contract["decision_confidence"]:
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
    parser.add_argument("--response", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--review-id",
        default="EXTERNAL_TEXT_MATCHED_WAYBACK_INDEPENDENT_SECOND_REVIEW_V1",
    )
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {args.output}")
    packet = load_json(args.packet)
    response = load_json(args.response)
    packet_hash = sha256_file(args.packet)
    if response.get("packet_sha256") != packet_hash:
        raise ValueError("Blind second-review packet SHA-256 mismatch")
    reviews = validate_reviews(packet, response)
    output = {
        "review_id": args.review_id,
        "status": "INDEPENDENT_BLINDED_AI_SECOND_REVIEW_COMPLETE",
        "inputs": {
            "packet": {"path": str(args.packet), "sha256": packet_hash},
            "response": {"path": str(args.response), "sha256": sha256_file(args.response)},
        },
        "counts": {
            "reviewed": len(reviews),
            "confirmed": sum(item["decision"] == "CONFIRMED" for item in reviews),
            "legitimate": sum(item["decision"] == "LEGITIMATE" for item in reviews),
            "uncertain": sum(item["decision"] == "UNCERTAIN" for item in reviews),
            "reject_capture": sum(item["decision"] == "REJECT_CAPTURE" for item in reviews),
        },
        "reviews": reviews,
        "safety_contract": {
            "mapping_exposed_to_reviewer": False,
            "first_review_exposed_to_reviewer": False,
            "model_outputs_exposed_to_reviewer": False,
            "independent_human_review_claimed": False,
            "labels_materialized": 0,
            "model_scoring_operations": 0,
            "training_allowed": False,
            "deployment_allowed": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
