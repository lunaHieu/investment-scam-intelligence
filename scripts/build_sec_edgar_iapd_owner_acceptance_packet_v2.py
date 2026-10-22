"""Build the hash-bound owner-acceptance packet for reconciliation V2."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


RECONCILIATION_ID = "ISI_SEC_EDGAR_IAPD_RECONCILIATION_V2"
RECONCILIATION_STATUS = "RECONCILED_RECOMMENDATIONS_COMPLETE_OWNER_ACCEPTANCE_REQUIRED"
RECONCILIATION_QA_STATUS = "PASS_CAPTURED_SUBSET_RECONCILIATION_REPRODUCED_OWNER_ACCEPTANCE_REQUIRED"
EXPECTED_COUNTS = {"LEGITIMATE": 42, "UNCERTAIN": 14}


def build(reconciliation_path: Path, reconciliation_qa_path: Path) -> dict[str, Any]:
    reconciliation = load_object(reconciliation_path)
    qa = load_object(reconciliation_qa_path)
    reconciliation_sha256 = sha256_file(reconciliation_path)
    reconciliation_qa_sha256 = sha256_file(reconciliation_qa_path)

    if reconciliation.get("reconciliation_id") != RECONCILIATION_ID:
        raise ValueError("Unexpected reconciliation identity")
    if reconciliation.get("status") != RECONCILIATION_STATUS:
        raise ValueError("Reconciliation is not ready for owner acceptance")
    if qa.get("status") != RECONCILIATION_QA_STATUS:
        raise ValueError("Reconciliation QA did not pass the captured-subset gate")
    if qa.get("inputs", {}).get("reconciliation_sha256") != reconciliation_sha256:
        raise ValueError("Reconciliation QA binding mismatch")
    if qa.get("decision", {}).get("owner_acceptance_required") is not True:
        raise ValueError("Reconciliation QA did not require owner acceptance")

    records = []
    record_ids: list[str] = []
    recommendation_counts: Counter[str] = Counter()
    for source in reconciliation.get("records", []):
        record_id = str(source.get("record_id"))
        recommendation = source.get("reconciled_recommendation")
        cohort = source.get("cohort")
        if recommendation not in EXPECTED_COUNTS:
            raise ValueError(f"Unexpected reconciled recommendation: {record_id}")
        if cohort not in {"DEVELOPMENT", "EXTERNAL_HOLDOUT"}:
            raise ValueError(f"Unexpected cohort: {record_id}")
        if source.get("owner_acceptance") != "PENDING":
            raise ValueError(f"Owner acceptance is not pending: {record_id}")
        if source.get("ground_truth_status") != "UNCERTAIN" or source.get("label_created") is not False:
            raise ValueError(f"Reconciliation prematurely materialized a label: {record_id}")
        if source.get("training_eligible") != "NO":
            raise ValueError(f"Reconciliation prematurely opened training: {record_id}")
        record_ids.append(record_id)
        recommendation_counts[recommendation] += 1
        records.append({
            "record_id": record_id,
            "reconciled_recommendation": recommendation,
            "review_agreement": source.get("review_agreement"),
            "accepted": None,
            "rationale": "",
        })

    if len(record_ids) != len(set(record_ids)):
        raise ValueError("Duplicate record IDs in reconciliation")
    if dict(recommendation_counts) != EXPECTED_COUNTS:
        raise ValueError(f"Unexpected frozen recommendation counts: {dict(recommendation_counts)}")

    return {
        "acceptance_id": "ISI_SEC_EDGAR_IAPD_OWNER_ACCEPTANCE_V2",
        "status": "PENDING_OWNER_DECISIONS",
        "reconciliation_sha256": reconciliation_sha256,
        "reconciliation_qa_sha256": reconciliation_qa_sha256,
        "owner_attestation": {
            "reviewed_reconciliation_snapshot": False,
            "explicit_acceptance": False,
            "independent_evidence_rereview_claimed": False,
        },
        "instructions": {
            "set_status_after_review": "OWNER_DECISIONS_COMPLETE",
            "complete_every_accepted_boolean": True,
            "minimum_rationale_characters": 40,
            "uncertain_records_must_not_be_accepted": True,
            "cohort_must_not_be_added_or_changed": True,
        },
        "records": records,
        "decision": {
            "owner_review_complete": False,
            "label_materialization_allowed": False,
            "training_allowed": False,
        },
        "safety_contract": {
            "network_operations": 0,
            "model_operations": 0,
            "labels_created": 0,
            "training_operations": 0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reconciliation", type=Path, required=True)
    parser.add_argument("--reconciliation-qa", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite owner-acceptance packet")
    result = build(args.reconciliation, args.reconciliation_qa)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({"acceptance_id": result["acceptance_id"], "status": result["status"], "record_count": len(result["records"]), "output": str(args.output), "sha256": sha256_file(args.output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
