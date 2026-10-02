"""Validate and freeze an independent blinded AI second review for Wayback holdout V3."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.record_wayback_language_second_review_v2 import validate_reviews
from src.isi.normalization.external_references import sha256_file


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
    if packet.get("packet_id") != "EXTERNAL_TEXT_WAYBACK_HOLDOUT_BLIND_SECOND_REVIEW_V3":
        raise ValueError("Unexpected V3 blind packet ID")
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
        "review_id": "EXTERNAL_TEXT_WAYBACK_HOLDOUT_INDEPENDENT_SECOND_REVIEW_V3",
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
