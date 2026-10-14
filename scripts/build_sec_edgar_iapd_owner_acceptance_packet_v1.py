"""Build a pending, hash-bound SEC/IAPD owner-acceptance decision packet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


RECONCILIATION_QA_STATUS = "PASS_RECONCILIATION_REPRODUCED_OWNER_ACCEPTANCE_REQUIRED"


def build(reconciliation_path: Path, reconciliation_qa_path: Path) -> dict[str, Any]:
    reconciliation = load_object(reconciliation_path)
    qa = load_object(reconciliation_qa_path)
    if reconciliation.get("status") != "RECONCILED_RECOMMENDATIONS_COMPLETE_OWNER_ACCEPTANCE_REQUIRED":
        raise ValueError("Reconciliation is not ready for owner acceptance")
    if qa.get("status") != RECONCILIATION_QA_STATUS:
        raise ValueError("Reconciliation QA did not pass")
    if qa.get("inputs", {}).get("reconciliation_sha256") != sha256_file(reconciliation_path):
        raise ValueError("Reconciliation QA binding mismatch")
    if qa.get("decision", {}).get("owner_acceptance_required") is not True:
        raise ValueError("Reconciliation QA did not require owner acceptance")

    records = []
    for source in reconciliation.get("records", []):
        recommendation = source.get("reconciled_recommendation")
        if recommendation not in {"LEGITIMATE", "UNCERTAIN"}:
            raise ValueError(f"Unexpected reconciled recommendation: {source.get('record_id')}")
        records.append({
            "record_id": source["record_id"],
            "reconciled_recommendation": recommendation,
            "review_agreement": source.get("review_agreement"),
            "accepted": None,
            "rationale": "",
        })

    return {
        "acceptance_id": "ISI_SEC_EDGAR_IAPD_OWNER_ACCEPTANCE_V1",
        "status": "PENDING_OWNER_DECISIONS",
        "reconciliation_sha256": sha256_file(reconciliation_path),
        "reconciliation_qa_sha256": sha256_file(reconciliation_qa_path),
        "owner_attestation": {
            "reviewed_reconciliation": False,
            "explicit_acceptance": False,
        },
        "instructions": {
            "set_status_after_review": "OWNER_DECISIONS_COMPLETE",
            "set_both_attestations_true_only_after_review": True,
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
