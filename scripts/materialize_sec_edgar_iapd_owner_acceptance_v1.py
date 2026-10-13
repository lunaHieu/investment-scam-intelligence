"""Materialize explicitly accepted SEC/IAPD reconciled recommendations safely."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


RECONCILIATION_QA_STATUS = "PASS_RECONCILIATION_REPRODUCED_OWNER_ACCEPTANCE_REQUIRED"


def build(reconciliation_path: Path, reconciliation_qa_path: Path, acceptance_path: Path) -> dict[str, Any]:
    reconciliation = load_object(reconciliation_path)
    qa = load_object(reconciliation_qa_path)
    acceptance = load_object(acceptance_path)
    if qa.get("status") != RECONCILIATION_QA_STATUS or qa.get("inputs", {}).get("reconciliation_sha256") != sha256_file(reconciliation_path):
        raise ValueError("Reconciliation QA status or binding mismatch")
    if qa.get("decision", {}).get("owner_acceptance_required") is not True:
        raise ValueError("Reconciliation QA did not require owner acceptance")
    if acceptance.get("acceptance_id") != "ISI_SEC_EDGAR_IAPD_OWNER_ACCEPTANCE_V1":
        raise ValueError("Unexpected owner acceptance identity")
    if acceptance.get("reconciliation_sha256") != sha256_file(reconciliation_path):
        raise ValueError("Owner acceptance is not bound to the frozen reconciliation")
    if acceptance.get("owner_attestation", {}).get("reviewed_reconciliation") is not True or acceptance.get("owner_attestation", {}).get("explicit_acceptance") is not True:
        raise ValueError("Owner attestation is incomplete")
    reconciled = {row["record_id"]: row for row in reconciliation.get("records", [])}
    decisions = list(acceptance.get("records", []))
    decision_ids = [str(row.get("record_id")) for row in decisions]
    if len(decision_ids) != len(set(decision_ids)) or set(decision_ids) != set(reconciled):
        raise ValueError("Owner acceptance population differs from reconciliation")
    outputs = []
    rejected = 0
    for decision in decisions:
        record_id = str(decision["record_id"])
        source = reconciled[record_id]
        if "cohort" in decision:
            raise ValueError(f"Owner acceptance must not redefine cohort: {record_id}")
        accepted = decision.get("accepted")
        if not isinstance(accepted, bool):
            raise ValueError(f"Acceptance decision is not boolean: {record_id}")
        if not isinstance(decision.get("rationale"), str) or len(decision["rationale"].strip()) < 40:
            raise ValueError(f"Owner acceptance lacks substantive rationale: {record_id}")
        if accepted and source["reconciled_recommendation"] != "LEGITIMATE":
            raise ValueError(f"Cannot accept a non-LEGITIMATE recommendation: {record_id}")
        if not accepted:
            rejected += 1
            continue
        cohort = str(source.get("cohort"))
        if cohort not in {"DEVELOPMENT", "EXTERNAL_HOLDOUT"}:
            raise ValueError(f"Invalid accepted cohort: {record_id}")
        outputs.append({
            "record_id": record_id,
            "cohort": cohort,
            "accepted_recommendation": "LEGITIMATE",
            "ground_truth_status": "LEGITIMATE",
            "evidence_confidence": "HIGH_RECONCILED_OWNER_ACCEPTED",
            "label_created": True,
            "training_eligible": "NO_PENDING_BALANCED_DATASET_RELEASE" if cohort == "DEVELOPMENT" else "NO_EXTERNAL_HOLDOUT",
            "model_scoring_eligible": "NO_PENDING_FROZEN_EVALUATION_RELEASE" if cohort == "EXTERNAL_HOLDOUT" else "NO",
            "owner_acceptance_rationale": decision["rationale"],
            "provenance": {"reconciliation_sha256": sha256_file(reconciliation_path), "reconciliation_qa_sha256": sha256_file(reconciliation_qa_path), "owner_acceptance_sha256": sha256_file(acceptance_path)},
        })
    counts = Counter(row["cohort"] for row in outputs)
    return {
        "materialization_id": "ISI_SEC_EDGAR_IAPD_OWNER_ACCEPTED_RECORDS_V1",
        "status": "OWNER_ACCEPTED_LABELS_MATERIALIZED_DATASET_RELEASE_REQUIRED",
        "inputs": {"reconciliation_sha256": sha256_file(reconciliation_path), "reconciliation_qa_sha256": sha256_file(reconciliation_qa_path), "owner_acceptance_sha256": sha256_file(acceptance_path)},
        "records": outputs,
        "summary": {"reconciliation_records": len(reconciled), "accepted_records": len(outputs), "rejected_or_deferred_records": rejected, "accepted_by_cohort": dict(sorted(counts.items())), "labels_created": len(outputs), "training_eligible_records": 0},
        "decision": {"owner_acceptance_materialized": True, "balanced_dataset_release_required": True, "development_training_allowed_now": False, "external_holdout_training_allowed": False, "model_scoring_allowed_now": False},
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
