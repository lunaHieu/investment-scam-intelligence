"""Verify blind second-review coverage, structure, and closed gates."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object: {path}")
    return value


def verify(config_path: Path, review_path: Path) -> dict[str, Any]:
    config = load(config_path)
    packet_path = Path(config["outputs"]["blind_packet"])
    packet = load(packet_path)
    review = load(review_path)
    errors: list[str] = []
    if review.get("input_packet", {}).get("sha256") != sha(packet_path):
        errors.append("Blind packet hash mismatch")
    packet_rows = {row["blind_id"]: row for row in packet.get("records", [])}
    review_rows = review.get("records", [])
    review_ids = [str(row.get("blind_id")) for row in review_rows]
    if len(review_ids) != len(set(review_ids)):
        errors.append("Duplicate blind ID")
    if set(review_ids) != set(packet_rows) or len(review_ids) != config["expected_review_population"]:
        errors.append("Second-review population differs from blind packet")
    serialized_review = json.dumps(review, ensure_ascii=False).casefold()
    for forbidden in ("candidate_id", "channel_target_stratum", "primary_recommendation", "primary rationale"):
        if forbidden in serialized_review:
            errors.append(f"Second-review output contains forbidden primary or identity field: {forbidden}")

    allowed = set(config["review_scope"]["allowed_second_recommendations"])
    assessment_values = {"PASS", "FAIL", "UNCERTAIN", "NOT_APPLICABLE"}
    counts: Counter[str] = Counter()
    for row in review_rows:
        blind_id = str(row.get("blind_id"))
        recommendation = str(row.get("second_recommendation"))
        counts[recommendation] += 1
        if recommendation not in allowed:
            errors.append(f"Invalid recommendation: {blind_id}")
            continue
        assessments = row.get("assessments", {})
        for name in config["review_scope"]["required_assessments"]:
            if assessments.get(name) not in assessment_values:
                errors.append(f"Invalid or missing {name}: {blind_id}")
        facts = row.get("supporting_facts", [])
        if not isinstance(facts, list) or len(facts) < 2 or any(not isinstance(item, str) or len(item.strip()) < 12 for item in facts):
            errors.append(f"Insufficient supporting facts: {blind_id}")
        if not isinstance(row.get("rationale"), str) or len(row["rationale"].strip()) < 80:
            errors.append(f"Missing substantive rationale: {blind_id}")
        if row.get("ground_truth_status") != "UNCERTAIN" or row.get("label_created") is not False or row.get("training_eligible") != "NO":
            errors.append(f"Second review created a label or enabled training: {blind_id}")
        all_pass = all(assessments.get(name) == "PASS" for name in config["review_scope"]["required_assessments"])
        evidence = packet_rows.get(blind_id, {}).get("official_evidence", {})
        uncertainty = row.get("uncertainty_reasons", [])
        if recommendation == "CONFIRMED" and ("warning_reference" not in evidence or not all_pass):
            errors.append(f"CONFIRMED gate not met: {blind_id}")
        if recommendation == "LEGITIMATE" and ("registration_reference" not in evidence or not all_pass):
            errors.append(f"LEGITIMATE gate not met: {blind_id}")
        if recommendation == "UNCERTAIN":
            if all_pass:
                errors.append(f"UNCERTAIN lacks non-pass assessment: {blind_id}")
            if not isinstance(uncertainty, list) or not uncertainty:
                errors.append(f"UNCERTAIN lacks reasons: {blind_id}")
        elif uncertainty:
            errors.append(f"Decisive recommendation retains uncertainty reasons: {blind_id}")
    expected_summary = {
        "reviewed_records": len(review_rows),
        "second_recommendation_counts": dict(sorted(counts.items())),
        "labels_created": 0,
        "training_eligible_records": 0,
    }
    if review.get("summary") != expected_summary:
        errors.append(f"Review summary mismatch: {review.get('summary')} != {expected_summary}")
    reviewer = review.get("reviewer", {})
    for key in ("primary_result_accessed", "private_mapping_accessed", "model_predictions_visible", "network_access_used"):
        if reviewer.get(key) is not False:
            errors.append(f"Blinding/safety declaration is not false: {key}")
    return {
        "review_id": "ISI_TARGET_TEXT_CORPUS_V1_BLIND_SECOND_REVIEW_STRUCTURAL_QA_V1",
        "status": "PASS_BLIND_STRUCTURE_SCOPE_AND_CONSERVATIVE_GATES" if not errors else "FAIL",
        "inputs": {
            "config": {"path": str(config_path), "sha256": sha(config_path)},
            "blind_packet": {"path": str(packet_path), "sha256": sha(packet_path)},
            "second_review": {"path": str(review_path), "sha256": sha(review_path)},
        },
        "checks": {
            "packet_population": len(packet_rows),
            "reviewed_population": len(review_ids),
            "second_recommendation_counts": dict(sorted(counts.items())),
            "labels_created": 0,
            "training_eligible_records": 0,
        },
        "decision": {
            "blind_second_review_structure_and_scope_passed": not errors,
            "reconciliation_allowed": not errors,
            "ground_truth_labeling_completed": False,
            "training_allowed": False,
        },
        "errors": errors,
        "safety_contract": config["safety_contract"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {args.output}")
    result = verify(args.config, args.review)
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
