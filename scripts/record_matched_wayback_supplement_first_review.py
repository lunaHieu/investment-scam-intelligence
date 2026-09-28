"""Validate and record AI primary decisions for matched-Wayback supplement candidates."""

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


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def validate_decisions(packet: dict[str, object], decisions: dict[str, object]) -> list[dict]:
    if decisions.get("review_type") != "AI_PRIMARY_REVIEW_NOT_HUMAN":
        raise ValueError("Review type must not claim human review")
    if decisions.get("model_outputs_consulted") is not False:
        raise ValueError("Model outputs must remain excluded from primary review")
    packet_items = {item["candidate_id"]: item for item in packet.get("items", [])}
    decision_items = {item["candidate_id"]: item for item in decisions.get("decisions", [])}
    if set(packet_items) != set(decision_items):
        raise ValueError("Decision IDs do not exactly cover the first-review packet")
    completed = []
    for candidate_id in sorted(packet_items):
        source = packet_items[candidate_id]
        decision = decision_items[candidate_id]
        value = decision.get("decision")
        confidence = decision.get("confidence")
        contradictions = decision.get("contradictions", [])
        if value not in source.get("allowed_decisions", []):
            raise ValueError(f"Unsupported decision: {candidate_id}")
        if confidence not in {"HIGH", "MEDIUM", "LOW"}:
            raise ValueError(f"Unsupported confidence: {candidate_id}")
        if not str(decision.get("rationale", "")).strip():
            raise ValueError(f"Missing rationale: {candidate_id}")
        if value == "LEGITIMATE":
            screening = source["screening"]
            if screening.get("screening_decision") != "REVIEWABLE_OBSERVED_TEXT":
                raise ValueError(f"Target decision on a failed capture: {candidate_id}")
            if screening.get("snapshot_predates_registration") is not False:
                raise ValueError(f"Target decision predates registration: {candidate_id}")
            if contradictions:
                raise ValueError(f"Target decision retains contradictions: {candidate_id}")
            if confidence != "HIGH":
                raise ValueError(f"Target decision must be high confidence: {candidate_id}")
        completed.append(
            {
                "candidate_id": candidate_id,
                "artifact_text_sha256": source["artifact"]["text_sha256"],
                "capture_sha256": source["artifact"]["source_capture_sha256"],
                "decision": value,
                "confidence": confidence,
                "rationale": decision["rationale"],
                "contradictions": contradictions,
                "reviewer": decisions["reviewer"],
                "reviewed_at": decisions["reviewed_at"],
                "review_type": decisions["review_type"],
                "ready_for_independent_second_review": value == "LEGITIMATE" and confidence == "HIGH",
                "ground_truth_label_created": False,
                "benchmark_eligible": False,
            }
        )
    return completed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {args.output}")
    packet = load_json(args.packet)
    decisions = load_json(args.decisions)
    actual_packet_hash = sha256_file(args.packet)
    if decisions.get("source_packet_sha256") != actual_packet_hash:
        raise ValueError("First-review packet SHA-256 mismatch")
    completed = validate_decisions(packet, decisions)
    output = {
        "review_id": decisions["review_id"],
        "status": "AI_PRIMARY_REVIEW_COMPLETE_SECOND_REVIEW_REQUIRED",
        "inputs": {
            "packet": {"path": str(args.packet), "sha256": actual_packet_hash},
            "decisions": {"path": str(args.decisions), "sha256": sha256_file(args.decisions)},
        },
        "counts": {
            "reviewed": len(completed),
            "legitimate_high": sum(
                item["decision"] == "LEGITIMATE" and item["confidence"] == "HIGH"
                for item in completed
            ),
            "uncertain": sum(item["decision"] == "UNCERTAIN" for item in completed),
            "benchmark_eligible": 0,
        },
        "reviews": completed,
        "safety_contract": {
            "independent_human_review_claimed": False,
            "ground_truth_labels_created": 0,
            "model_scoring_operations": 0,
            "second_review_required": True,
            "training_allowed": False,
            "deployment_allowed": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
