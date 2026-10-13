"""Validate SEC/IAPD primary evidence review before blind second review."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


ASSESSMENTS = {"identity_linkage", "task_relevance", "capture_chronology", "repurpose_or_parking", "contradiction_screen"}


def verify(packet_path: Path, review_path: Path) -> dict[str, Any]:
    packet = load_object(packet_path)
    review = load_object(review_path)
    errors: list[str] = []
    if packet.get("packet_id") != "ISI_SEC_EDGAR_IAPD_PRIMARY_REVIEW_PACKET_V1":
        errors.append("Unexpected primary-review packet identity")
    if review.get("input_packet", {}).get("sha256") != sha256_file(packet_path):
        errors.append("Primary review packet hash mismatch")
    packet_ids = {row["record_id"] for row in packet.get("records", [])}
    rows = list(review.get("records", []))
    ids = [str(row.get("record_id")) for row in rows]
    if len(ids) != len(set(ids)) or set(ids) != packet_ids:
        errors.append("Primary review population differs from packet")
    counts: Counter[str] = Counter()
    for row in rows:
        record_id = str(row.get("record_id"))
        recommendation = row.get("primary_recommendation")
        counts[str(recommendation)] += 1
        if recommendation not in {"LEGITIMATE", "UNCERTAIN"}:
            errors.append(f"Invalid primary recommendation: {record_id}")
        assessments = row.get("assessments", {})
        if set(assessments) != ASSESSMENTS or any(value not in {"PASS", "FAIL", "UNCERTAIN"} for value in assessments.values()):
            errors.append(f"Invalid primary assessments: {record_id}")
        facts = row.get("supporting_facts", [])
        uncertainty = row.get("uncertainty_reasons", [])
        rationale = row.get("rationale")
        if not isinstance(rationale, str) or len(rationale.strip()) < 80:
            errors.append(f"Missing substantive primary rationale: {record_id}")
        if recommendation == "LEGITIMATE" and (set(assessments.values()) != {"PASS"} or len(facts) < 2 or uncertainty):
            errors.append(f"LEGITIMATE recommendation lacks complete affirmative evidence: {record_id}")
        if recommendation == "UNCERTAIN" and not uncertainty:
            errors.append(f"UNCERTAIN recommendation lacks an uncertainty reason: {record_id}")
        if row.get("ground_truth_status") != "UNCERTAIN" or row.get("label_created") is not False or row.get("training_eligible") != "NO":
            errors.append(f"Primary review created a label or training eligibility: {record_id}")
    reviewer = review.get("reviewer", {})
    if reviewer.get("network_access_used") is not False or reviewer.get("model_predictions_visible") is not False or reviewer.get("source_membership_treated_as_ground_truth") is not False:
        errors.append("Primary-review firewall was not preserved")
    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_PRIMARY_REVIEW_STRUCTURAL_QA_V1",
        "status": "PASS_PRIMARY_REVIEW_BLIND_SECOND_REVIEW_MAY_BE_PREPARED" if not errors else "FAIL",
        "inputs": {"packet_sha256": sha256_file(packet_path), "review_sha256": sha256_file(review_path)},
        "checks": {"packet_population": len(packet_ids), "reviewed_population": len(ids), "recommendation_counts": dict(sorted(counts.items())), "labels_created": 0},
        "decision": {"primary_review_structure_passed": not errors, "blind_second_review_may_be_prepared": not errors, "ground_truth_labeling_completed": False, "training_allowed": False},
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
        raise FileExistsError("Refusing to overwrite primary-review QA")
    result = verify(args.packet, args.review)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
