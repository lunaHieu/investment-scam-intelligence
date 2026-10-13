"""Validate bounded SEC/IAPD manual group decisions without creating labels."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


ALLOWED = {"KEEP_PROVISIONALLY_DISTINCT", "MERGE_TECHNICAL_GROUPS", "ROUTE_OPENED_COHORT_CLONE_REVIEW", "CONFIRM_AUTOMATED_EXCLUSION", "UNRESOLVED_GROUP_RELATIONSHIP"}
AUTOMATED_EXCLUSIONS = {"EXCLUDED_OPENED_COHORT_EXACT_OR_HOST_OVERLAP", "EXCLUDED_HOLDOUT_CROSS_COHORT_COLLISION"}


def verify(packet_path: Path, review_path: Path) -> dict[str, Any]:
    packet = load_object(packet_path)
    review = load_object(review_path)
    errors: list[str] = []
    if packet.get("packet_id") != "ISI_SEC_EDGAR_IAPD_MANUAL_GROUP_REVIEW_PACKET_V1" or packet.get("status") != "FROZEN_UNREVIEWED_PACKET":
        errors.append("Unexpected manual-review packet identity or status")
    if review.get("input_packet", {}).get("sha256") != sha256_file(packet_path):
        errors.append("Manual review is not bound to the frozen packet")
    packet_by_id = {row["record_id"]: row for row in packet.get("records", [])}
    rows = list(review.get("records", []))
    ids = [str(row.get("record_id")) for row in rows]
    if len(ids) != len(set(ids)) or set(ids) != set(packet_by_id):
        errors.append("Manual-review population differs from packet")
    counts: Counter[str] = Counter()
    primary_candidates = 0
    for row in rows:
        record_id = str(row.get("record_id"))
        source = packet_by_id.get(record_id, {})
        decision = row.get("group_decision")
        counts[str(decision)] += 1
        if decision not in ALLOWED:
            errors.append(f"Invalid group decision: {record_id}")
        if not isinstance(row.get("rationale"), str) or len(row["rationale"].strip()) < 40:
            errors.append(f"Missing substantive rationale: {record_id}")
        if row.get("ground_truth_status") != "UNCERTAIN" or row.get("label_created") is not False or row.get("training_eligible") != "NO":
            errors.append(f"Group review created a label or training eligibility: {record_id}")
        linked = row.get("linked_record_ids", [])
        opened = row.get("linked_opened_record_keys", [])
        evidence = row.get("positive_linkage_evidence", [])
        if decision == "MERGE_TECHNICAL_GROUPS" and (not linked or not evidence):
            errors.append(f"Merge lacks named record and positive evidence: {record_id}")
        canonical = row.get("canonical_record_id")
        if decision == "MERGE_TECHNICAL_GROUPS" and canonical not in {record_id, *linked}:
            errors.append(f"Merge lacks a valid canonical record: {record_id}")
        if decision == "ROUTE_OPENED_COHORT_CLONE_REVIEW" and (not opened or not evidence):
            errors.append(f"Opened-clone route lacks named record and positive evidence: {record_id}")
        routing = source.get("automated_screen", {}).get("routing_decision")
        if routing in AUTOMATED_EXCLUSIONS and decision not in {"CONFIRM_AUTOMATED_EXCLUSION", "ROUTE_OPENED_COHORT_CLONE_REVIEW", "UNRESOLVED_GROUP_RELATIONSHIP"}:
            errors.append(f"Review attempted to reinstate an automated exclusion: {record_id}")
        if decision == "KEEP_PROVISIONALLY_DISTINCT" and (linked or opened or evidence):
            errors.append(f"Distinct decision contains contradictory linkage: {record_id}")
        if decision == "KEEP_PROVISIONALLY_DISTINCT" or (decision == "MERGE_TECHNICAL_GROUPS" and canonical == record_id):
            primary_candidates += 1
    reviewer = review.get("reviewer", {})
    if reviewer.get("network_access_used") is not False or reviewer.get("model_predictions_visible") is not False or reviewer.get("source_membership_treated_as_label") is not False:
        errors.append("Reviewer scope firewall was not preserved")
    unresolved = counts["UNRESOLVED_GROUP_RELATIONSHIP"]
    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_MANUAL_GROUP_REVIEW_STRUCTURAL_QA_V1",
        "status": "PASS_GROUP_REVIEW_PRIMARY_PACKET_MAY_BE_PREPARED" if not errors and unresolved == 0 else ("PASS_GROUP_REVIEW_UNRESOLVED_PRIMARY_BLOCKED" if not errors else "FAIL"),
        "inputs": {"packet_sha256": sha256_file(packet_path), "review_sha256": sha256_file(review_path)},
        "checks": {"packet_population": len(packet_by_id), "reviewed_population": len(ids), "decision_counts": dict(sorted(counts.items())), "unresolved_relationships": unresolved, "primary_review_candidate_count": primary_candidates, "labels_created": 0},
        "decision": {"group_review_structure_passed": not errors, "primary_review_packet_may_be_prepared": not errors and unresolved == 0, "binary_labeling_completed": False, "training_allowed": False},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "labels": 0, "model": 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite manual group-review QA")
    result = verify(args.packet, args.review)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
