"""Materialize only owner-accepted SEC/IAPD V2 recommendations."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.build_sec_edgar_iapd_owner_acceptance_packet_v2 import RECONCILIATION_ID, RECONCILIATION_QA_STATUS
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def build(reconciliation_path: Path, reconciliation_qa_path: Path, acceptance_path: Path) -> dict[str, Any]:
    reconciliation = load_object(reconciliation_path)
    qa = load_object(reconciliation_qa_path)
    acceptance = load_object(acceptance_path)
    reconciliation_sha256 = sha256_file(reconciliation_path)
    reconciliation_qa_sha256 = sha256_file(reconciliation_qa_path)
    acceptance_sha256 = sha256_file(acceptance_path)

    if reconciliation.get("reconciliation_id") != RECONCILIATION_ID:
        raise ValueError("Unexpected reconciliation identity")
    if qa.get("status") != RECONCILIATION_QA_STATUS or qa.get("inputs", {}).get("reconciliation_sha256") != reconciliation_sha256:
        raise ValueError("Reconciliation QA status or binding mismatch")
    if qa.get("decision", {}).get("owner_acceptance_required") is not True:
        raise ValueError("Reconciliation QA did not require owner acceptance")
    if acceptance.get("acceptance_id") != "ISI_SEC_EDGAR_IAPD_OWNER_ACCEPTANCE_V2" or acceptance.get("status") != "OWNER_DECISIONS_COMPLETE":
        raise ValueError("Owner acceptance decisions are not complete")
    if acceptance.get("reconciliation_sha256") != reconciliation_sha256 or acceptance.get("reconciliation_qa_sha256") != reconciliation_qa_sha256:
        raise ValueError("Owner acceptance is not bound to the frozen reconciliation and QA")
    attestation = acceptance.get("owner_attestation", {})
    if attestation.get("reviewed_reconciliation_snapshot") is not True or attestation.get("explicit_acceptance") is not True:
        raise ValueError("Owner attestation is incomplete")
    if attestation.get("independent_evidence_rereview_claimed") is not False:
        raise ValueError("Owner acceptance overclaims independent review")

    reconciled = {row["record_id"]: row for row in reconciliation.get("records", [])}
    decisions = list(acceptance.get("records", []))
    decision_ids = [str(row.get("record_id")) for row in decisions]
    if len(decision_ids) != len(set(decision_ids)) or set(decision_ids) != set(reconciled):
        raise ValueError("Owner acceptance population differs from reconciliation")

    accepted_records = []
    deferred_records = []
    for decision in decisions:
        record_id = str(decision["record_id"])
        source = reconciled[record_id]
        if "cohort" in decision:
            raise ValueError(f"Owner acceptance must not redefine cohort: {record_id}")
        if decision.get("reconciled_recommendation") != source.get("reconciled_recommendation"):
            raise ValueError(f"Owner acceptance recommendation context mismatch: {record_id}")
        if decision.get("review_agreement") != source.get("review_agreement"):
            raise ValueError(f"Owner acceptance agreement context mismatch: {record_id}")
        accepted = decision.get("accepted")
        rationale = decision.get("rationale")
        if not isinstance(accepted, bool):
            raise ValueError(f"Acceptance decision is not boolean: {record_id}")
        if not isinstance(rationale, str) or len(rationale.strip()) < 40:
            raise ValueError(f"Owner acceptance lacks substantive rationale: {record_id}")
        if accepted and source["reconciled_recommendation"] != "LEGITIMATE":
            raise ValueError(f"Cannot accept a non-LEGITIMATE recommendation: {record_id}")
        if not accepted and source["reconciled_recommendation"] != "UNCERTAIN":
            raise ValueError(f"A reconciled LEGITIMATE record was rejected outside the frozen authorization policy: {record_id}")
        cohort = str(source.get("cohort"))
        if cohort not in {"DEVELOPMENT", "EXTERNAL_HOLDOUT"}:
            raise ValueError(f"Invalid cohort: {record_id}")
        provenance = {
            "reconciliation_sha256": reconciliation_sha256,
            "reconciliation_qa_sha256": reconciliation_qa_sha256,
            "owner_acceptance_sha256": acceptance_sha256,
        }
        if accepted:
            accepted_records.append({
                "record_id": record_id,
                "cohort": cohort,
                "accepted_recommendation": "LEGITIMATE",
                "ground_truth_status": "LEGITIMATE",
                "evidence_confidence": "HIGH_RECONCILED_OWNER_ACCEPTED",
                "label_created": True,
                "training_eligible": "NO_PENDING_BALANCED_DATASET_RELEASE" if cohort == "DEVELOPMENT" else "NO_EXTERNAL_HOLDOUT",
                "model_scoring_eligible": "NO_PENDING_FROZEN_EVALUATION_RELEASE" if cohort == "EXTERNAL_HOLDOUT" else "NO",
                "owner_acceptance_rationale": rationale,
                "provenance": provenance,
            })
        else:
            deferred_records.append({
                "record_id": record_id,
                "cohort": cohort,
                "reconciled_recommendation": "UNCERTAIN",
                "ground_truth_status": "UNCERTAIN",
                "label_created": False,
                "training_eligible": "NO",
                "model_scoring_eligible": "NO",
                "owner_acceptance_rationale": rationale,
                "provenance": provenance,
            })

    accepted_counts = Counter(row["cohort"] for row in accepted_records)
    deferred_counts = Counter(row["cohort"] for row in deferred_records)
    return {
        "materialization_id": "ISI_SEC_EDGAR_IAPD_OWNER_ACCEPTED_RECORDS_V2",
        "status": "OWNER_ACCEPTED_LABELS_MATERIALIZED_DATASET_RELEASE_REQUIRED",
        "inputs": {
            "reconciliation_sha256": reconciliation_sha256,
            "reconciliation_qa_sha256": reconciliation_qa_sha256,
            "owner_acceptance_sha256": acceptance_sha256,
        },
        "records": accepted_records,
        "deferred_records": deferred_records,
        "summary": {
            "reconciliation_records": len(reconciled),
            "accepted_records": len(accepted_records),
            "uncertain_retained": len(deferred_records),
            "accepted_by_cohort": dict(sorted(accepted_counts.items())),
            "uncertain_by_cohort": dict(sorted(deferred_counts.items())),
            "labels_created": len(accepted_records),
            "training_eligible_records": 0,
        },
        "decision": {
            "owner_acceptance_materialized": True,
            "balanced_dataset_release_required": True,
            "development_training_allowed_now": False,
            "external_holdout_training_allowed": False,
            "model_scoring_allowed_now": False,
        },
        "safety_contract": {"network_operations": 0, "model_operations": 0, "training_operations": 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reconciliation", type=Path, required=True)
    parser.add_argument("--reconciliation-qa", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite owner-accepted materialization")
    result = build(args.reconciliation, args.reconciliation_qa, args.acceptance)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({"materialization_id": result["materialization_id"], "summary": result["summary"], "output": str(args.output), "sha256": sha256_file(args.output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
