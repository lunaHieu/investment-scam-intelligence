"""Structurally verify the bounded manual group-review result without relabeling it."""

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
    review = load(review_path)
    packet_path = Path(config["outputs"]["review_packet"])
    packet = load(packet_path)
    errors: list[str] = []
    if review.get("input_packet", {}).get("sha256") != sha(packet_path):
        errors.append("Review packet hash mismatch")
    packet_ids = {row["candidate_id"] for row in packet.get("records", [])}
    review_rows = review.get("records", [])
    review_ids = [str(row.get("candidate_id")) for row in review_rows]
    if len(review_ids) != len(set(review_ids)):
        errors.append("Duplicate reviewed candidate ID")
    if set(review_ids) != packet_ids or len(review_ids) != config["expected_review_population"]:
        errors.append("Review population differs from packet")
    allowed = set(config["review_scope"]["allowed_decisions"])
    counts: Counter[str] = Counter()
    flagged = 0
    for row in review_rows:
        candidate_id = str(row.get("candidate_id"))
        decision = row.get("group_decision")
        counts[str(decision)] += 1
        if decision not in allowed:
            errors.append(f"Invalid group decision: {candidate_id}")
        if not isinstance(row.get("rationale"), str) or len(row["rationale"].strip()) < 40:
            errors.append(f"Missing substantive rationale: {candidate_id}")
        if row.get("ground_truth_status") != "UNCERTAIN" or row.get("label_created") is not False:
            errors.append(f"Review created or changed a label: {candidate_id}")
        linked_candidates = row.get("linked_candidate_ids", [])
        linked_opened = row.get("linked_opened_record_keys", [])
        linkage = row.get("positive_linkage_evidence", [])
        if decision == "MERGE_TECHNICAL_GROUPS" and (not linked_candidates or not linkage):
            errors.append(f"Merge lacks named candidate and positive evidence: {candidate_id}")
        if decision == "ROUTE_OPENED_COHORT_CLONE_REVIEW" and (not linked_opened or not linkage):
            errors.append(f"Opened-clone route lacks named record and positive evidence: {candidate_id}")
        if decision == "KEEP_PROVISIONALLY_DISTINCT" and (linked_candidates or linked_opened or linkage):
            errors.append(f"Distinct decision contains contradictory linkage: {candidate_id}")
        flags = row.get("identity_or_content_flags_for_downstream_review", [])
        if not isinstance(flags, list):
            errors.append(f"Downstream flags are not a list: {candidate_id}")
        elif flags:
            flagged += 1
    summary = review.get("summary", {})
    expected_summary = {
        "keep_provisionally_distinct": counts["KEEP_PROVISIONALLY_DISTINCT"],
        "merge_technical_groups": counts["MERGE_TECHNICAL_GROUPS"],
        "route_opened_cohort_clone_review": counts["ROUTE_OPENED_COHORT_CLONE_REVIEW"],
        "unresolved_group_relationship": counts["UNRESOLVED_GROUP_RELATIONSHIP"],
        "records_with_downstream_identity_or_content_flags": flagged,
        "labels_created": 0,
    }
    if summary != expected_summary:
        errors.append(f"Review summary mismatch: {summary} != {expected_summary}")
    if review.get("reviewer", {}).get("network_access_used") is not False:
        errors.append("Manual review unexpectedly used network access")
    if review.get("reviewer", {}).get("model_predictions_visible") is not False:
        errors.append("Manual reviewer unexpectedly received model predictions")
    decision = review.get("decision", {})
    if decision.get("binary_labeling_completed") is not False:
        errors.append("Review incorrectly claims binary labeling")
    return {
        "review_id": "ISI_TARGET_TEXT_CORPUS_V1_MANUAL_GROUP_PRIMARY_REVIEW_STRUCTURAL_QA_V1",
        "status": "PASS_STRUCTURE_AND_SCOPE" if not errors else "FAIL",
        "inputs": {
            "config": {"path": str(config_path), "sha256": sha(config_path)},
            "packet": {"path": str(packet_path), "sha256": sha(packet_path)},
            "primary_review": {"path": str(review_path), "sha256": sha(review_path)},
        },
        "checks": {
            "packet_population": len(packet_ids),
            "reviewed_population": len(review_ids),
            "decision_counts": dict(sorted(counts.items())),
            "records_with_downstream_identity_or_content_flags": flagged,
            "labels_created": 0,
        },
        "decision": {
            "manual_group_review_structure_passed": not errors,
            "primary_case_and_artifact_review_allowed": not errors and counts["UNRESOLVED_GROUP_RELATIONSHIP"] == 0,
            "binary_labeling_completed": False,
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
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
