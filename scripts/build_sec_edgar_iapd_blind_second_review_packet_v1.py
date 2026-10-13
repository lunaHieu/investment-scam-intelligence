"""Build a blind SEC/IAPD second-review packet with primary decisions omitted."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


PRIMARY_QA_STATUS = "PASS_PRIMARY_REVIEW_BLIND_SECOND_REVIEW_MAY_BE_PREPARED"


def build(primary_packet_path: Path, primary_review_path: Path, primary_qa_path: Path) -> dict[str, Any]:
    primary_packet = load_object(primary_packet_path)
    primary_review = load_object(primary_review_path)
    primary_qa = load_object(primary_qa_path)
    if primary_qa.get("status") != PRIMARY_QA_STATUS or primary_qa.get("decision", {}).get("blind_second_review_may_be_prepared") is not True:
        raise ValueError("Primary-review QA did not release blind packet preparation")
    if primary_qa.get("inputs", {}).get("packet_sha256") != sha256_file(primary_packet_path) or primary_qa.get("inputs", {}).get("review_sha256") != sha256_file(primary_review_path):
        raise ValueError("Primary-review QA input binding mismatch")
    primary_ids = {row["record_id"] for row in primary_review.get("records", [])}
    packet_ids = {row["record_id"] for row in primary_packet.get("records", [])}
    if primary_ids != packet_ids:
        raise ValueError("Primary review population differs from primary packet")
    records = []
    for source in primary_packet["records"]:
        records.append({
            "record_id": source["record_id"],
            "shortlist_id": source["shortlist_id"],
            "cohort": source["cohort"],
            "candidate_identity": source["candidate_identity"],
            "capture": source["capture"],
            "official_evidence": source["official_evidence"],
            "group_review": source["group_review"],
            "review_form": {
                "second_recommendation": "PENDING_BLIND_SECOND_REVIEW",
                "assessments": {"identity_linkage": "PENDING", "task_relevance": "PENDING", "capture_chronology": "PENDING", "repurpose_or_parking": "PENDING", "contradiction_screen": "PENDING"},
                "supporting_facts": [],
                "uncertainty_reasons": [],
                "rationale": None,
                "ground_truth_status": "UNCERTAIN",
                "label_created": False,
                "training_eligible": "NO",
            },
        })
    packet = {
        "packet_id": "ISI_SEC_EDGAR_IAPD_BLIND_SECOND_REVIEW_PACKET_V1",
        "status": "FROZEN_BLINDED_UNREVIEWED_PACKET",
        "inputs": {
            "primary_packet_sha256": sha256_file(primary_packet_path),
            "primary_review_sha256_commitment_only": sha256_file(primary_review_path),
            "primary_review_qa_sha256": sha256_file(primary_qa_path),
        },
        "blinding_contract": {
            "primary_recommendations_included": False,
            "primary_assessments_included": False,
            "primary_rationales_included": False,
            "primary_summary_included": False,
            "model_predictions_included": False,
        },
        "review_scope": {
            "allowed_recommendations": ["LEGITIMATE", "UNCERTAIN"],
            "legitimate_requires": primary_packet["review_scope"]["legitimate_requires"],
            "source_membership_alone_is_insufficient": True,
            "recommendation_is_not_a_final_label": True,
        },
        "record_count": len(records),
        "records": records,
        "safety_contract": {"network_operations": 0, "primary_decisions_visible": False, "model_predictions_visible": False, "labels_created": 0, "training_allowed": False},
    }
    serialized = json.dumps(packet, ensure_ascii=False)
    for forbidden in ('"primary_recommendation":', "PRIMARY_REVIEW_COMPLETE", '"recommendation_counts":'):
        if forbidden in serialized:
            raise ValueError(f"Blind packet leaked primary decision material: {forbidden}")
    return packet


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary-packet", type=Path, required=True)
    parser.add_argument("--primary-review", type=Path, required=True)
    parser.add_argument("--primary-qa", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite blind second-review packet")
    packet = build(args.primary_packet, args.primary_review, args.primary_qa)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({"packet_id": packet["packet_id"], "record_count": packet["record_count"], "output": str(args.output), "sha256": sha256_file(args.output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
