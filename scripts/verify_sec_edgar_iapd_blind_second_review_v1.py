"""Validate blinded SEC/IAPD second-review decisions before reconciliation."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.verify_sec_edgar_iapd_primary_review_v1 import ASSESSMENTS
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def verify(packet_path: Path, review_path: Path) -> dict[str, Any]:
    packet = load_object(packet_path)
    review = load_object(review_path)
    errors: list[str] = []
    if packet.get("packet_id") != "ISI_SEC_EDGAR_IAPD_BLIND_SECOND_REVIEW_PACKET_V1" or packet.get("status") != "FROZEN_BLINDED_UNREVIEWED_PACKET":
        errors.append("Unexpected blind packet identity or status")
    if packet.get("blinding_contract", {}).get("primary_recommendations_included") is not False:
        errors.append("Blind packet did not preserve primary-decision blinding")
    if review.get("input_packet", {}).get("sha256") != sha256_file(packet_path):
        errors.append("Second review packet hash mismatch")
    packet_ids = {row["record_id"] for row in packet.get("records", [])}
    rows = list(review.get("records", []))
    ids = [str(row.get("record_id")) for row in rows]
    if len(ids) != len(set(ids)) or set(ids) != packet_ids:
        errors.append("Second-review population differs from blind packet")
    counts: Counter[str] = Counter()
    for row in rows:
        record_id = str(row.get("record_id"))
        recommendation = row.get("second_recommendation")
        counts[str(recommendation)] += 1
        if recommendation not in {"LEGITIMATE", "UNCERTAIN"}:
            errors.append(f"Invalid second recommendation: {record_id}")
        assessments = row.get("assessments", {})
        if set(assessments) != ASSESSMENTS or any(value not in {"PASS", "FAIL", "UNCERTAIN"} for value in assessments.values()):
            errors.append(f"Invalid second-review assessments: {record_id}")
        facts = row.get("supporting_facts", [])
        uncertainty = row.get("uncertainty_reasons", [])
        rationale = row.get("rationale")
        if not isinstance(rationale, str) or len(rationale.strip()) < 80:
            errors.append(f"Missing substantive second-review rationale: {record_id}")
        if recommendation == "LEGITIMATE" and (set(assessments.values()) != {"PASS"} or len(facts) < 2 or uncertainty):
            errors.append(f"LEGITIMATE second recommendation lacks complete evidence: {record_id}")
        if recommendation == "UNCERTAIN" and not uncertainty:
            errors.append(f"UNCERTAIN second recommendation lacks a reason: {record_id}")
        if row.get("ground_truth_status") != "UNCERTAIN" or row.get("label_created") is not False or row.get("training_eligible") != "NO":
            errors.append(f"Second review created a label or training eligibility: {record_id}")
    reviewer = review.get("reviewer", {})
    if reviewer.get("primary_decisions_visible") is not False or reviewer.get("network_access_used") is not False or reviewer.get("model_predictions_visible") is not False or reviewer.get("source_membership_treated_as_ground_truth") is not False:
        errors.append("Blind second-review firewall was not preserved")
    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_BLIND_SECOND_REVIEW_STRUCTURAL_QA_V1",
        "status": "PASS_BLIND_SECOND_REVIEW_RECONCILIATION_MAY_BE_PREPARED" if not errors else "FAIL",
        "inputs": {"packet_sha256": sha256_file(packet_path), "review_sha256": sha256_file(review_path)},
        "checks": {"packet_population": len(packet_ids), "reviewed_population": len(ids), "recommendation_counts": dict(sorted(counts.items())), "primary_decisions_visible": False, "labels_created": 0},
        "decision": {"second_review_structure_passed": not errors, "reconciliation_may_be_prepared": not errors, "ground_truth_labeling_completed": False, "training_allowed": False},
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
        raise FileExistsError("Refusing to overwrite blind second-review QA")
    result = verify(args.packet, args.review)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
