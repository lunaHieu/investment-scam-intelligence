"""Deterministically reconcile frozen SEC/IAPD primary and blind reviews."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


PRIMARY_QA = "PASS_PRIMARY_REVIEW_BLIND_SECOND_REVIEW_MAY_BE_PREPARED"
SECOND_QA = "PASS_BLIND_SECOND_REVIEW_RECONCILIATION_MAY_BE_PREPARED"


def build(primary_path: Path, primary_qa_path: Path, second_path: Path, second_qa_path: Path) -> dict[str, Any]:
    primary = load_object(primary_path)
    primary_qa = load_object(primary_qa_path)
    second = load_object(second_path)
    second_qa = load_object(second_qa_path)
    if primary_qa.get("status") != PRIMARY_QA or primary_qa.get("inputs", {}).get("review_sha256") != sha256_file(primary_path):
        raise ValueError("Primary review QA status or binding mismatch")
    if second_qa.get("status") != SECOND_QA or second_qa.get("inputs", {}).get("review_sha256") != sha256_file(second_path):
        raise ValueError("Blind second review QA status or binding mismatch")
    primary_by_id = {row["record_id"]: row for row in primary.get("records", [])}
    second_by_id = {row["record_id"]: row for row in second.get("records", [])}
    if set(primary_by_id) != set(second_by_id):
        raise ValueError("Primary/second review population mismatch")
    records = []
    for record_id in sorted(primary_by_id):
        left = primary_by_id[record_id]["primary_recommendation"]
        right = second_by_id[record_id]["second_recommendation"]
        agreement = left == right
        recommendation = "LEGITIMATE" if left == right == "LEGITIMATE" else "UNCERTAIN"
        records.append({
            "record_id": record_id,
            "primary_recommendation": left,
            "blind_second_recommendation": right,
            "review_agreement": agreement,
            "reconciled_recommendation": recommendation,
            "reconciliation_rule": "AGREED_LEGITIMATE" if recommendation == "LEGITIMATE" else ("AGREED_UNCERTAIN" if agreement else "DISAGREEMENT_TO_UNCERTAIN"),
            "owner_acceptance": "PENDING",
            "ground_truth_status": "UNCERTAIN",
            "label_created": False,
            "training_eligible": "NO",
        })
    counts = Counter(row["reconciled_recommendation"] for row in records)
    disagreements = sum(not row["review_agreement"] for row in records)
    return {
        "reconciliation_id": "ISI_SEC_EDGAR_IAPD_RECONCILIATION_V1",
        "status": "RECONCILED_RECOMMENDATIONS_COMPLETE_OWNER_ACCEPTANCE_REQUIRED",
        "inputs": {"primary_review": {"path": str(primary_path.resolve()), "sha256": sha256_file(primary_path)}, "primary_qa": {"path": str(primary_qa_path.resolve()), "sha256": sha256_file(primary_qa_path)}, "blind_second_review": {"path": str(second_path.resolve()), "sha256": sha256_file(second_path)}, "blind_second_qa": {"path": str(second_qa_path.resolve()), "sha256": sha256_file(second_qa_path)}},
        "policy": {"agreed_legitimate_becomes_recommendation_only": True, "any_disagreement_becomes_uncertain": True, "any_uncertain_review_becomes_uncertain": True, "owner_acceptance_required_for_materialization": True},
        "records": records,
        "summary": {"record_count": len(records), "reconciled_recommendation_counts": dict(sorted(counts.items())), "review_disagreements": disagreements, "owner_acceptance_pending": len(records), "labels_created": 0, "training_eligible_records": 0},
        "decision": {"reconciliation_complete": True, "owner_acceptance_packet_may_be_prepared": True, "ground_truth_labeling_completed": False, "training_allowed": False},
        "safety_contract": {"network_operations": 0, "model_operations": 0, "labels_created": 0, "training_allowed": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary-review", type=Path, required=True)
    parser.add_argument("--primary-qa", type=Path, required=True)
    parser.add_argument("--second-review", type=Path, required=True)
    parser.add_argument("--second-qa", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite reconciliation")
    result = build(args.primary_review, args.primary_qa, args.second_review, args.second_qa)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({"reconciliation_id": result["reconciliation_id"], "summary": result["summary"], "output": str(args.output), "sha256": sha256_file(args.output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
