"""Materialize owner-accepted target-text pilot ground truth with training closed."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


EXPECTED_ACCEPTANCE_ID = "ISI_TARGET_TEXT_CORPUS_V1_OWNER_ACCEPTANCE_V1"
EXPECTED_RECONCILIATION_ID = "ISI_TARGET_TEXT_CORPUS_V1_RECONCILIATION_V1"
DECISIVE_LABELS = {"CONFIRMED", "LEGITIMATE"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def resolve(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def verified_input(root: Path, item: dict[str, Any], role: str) -> Path:
    path = resolve(root, item.get("path"))
    if not path.is_file():
        raise ValueError(f"Missing {role}: {path}")
    actual = sha256_file(path)
    if actual != item.get("sha256"):
        raise ValueError(f"Changed {role}: expected {item.get('sha256')}, got {actual}")
    return path


def materialize(acceptance_path: Path) -> dict[str, Any]:
    acceptance = load_object(acceptance_path)
    if acceptance.get("acceptance_id") != EXPECTED_ACCEPTANCE_ID:
        raise ValueError("Unexpected owner-acceptance ID")
    if acceptance.get("status") != "FROZEN_OWNER_ACCEPTANCE":
        raise ValueError("Owner acceptance is not frozen")

    contract = acceptance.get("acceptance_contract", {})
    required_true = (
        "accept_reconciled_recommendations",
        "materialize_decisive_ground_truth",
        "retain_uncertain_outside_binary_training",
        "opened_external_cohort_diagnostic_only",
    )
    if any(contract.get(key) is not True for key in required_true):
        raise ValueError("Acceptance contract is incomplete")
    prohibited = (
        "training_eligibility_granted",
        "model_scoring_allowed",
        "model_fit_allowed",
        "validation_or_test_opening_allowed",
    )
    if any(contract.get(key) is not False for key in prohibited):
        raise ValueError("Acceptance must keep training, scoring, fitting, and evaluation closed")

    root = acceptance_path.resolve().parents[1]
    scope = acceptance["scope"]
    registry_path = verified_input(root, scope["reconciliation_registry"], "reconciliation registry")
    reconciliation_path = verified_input(root, scope["reconciliation_artifact"], "reconciliation artifact")
    registry = load_object(registry_path)
    reconciliation = load_object(reconciliation_path)
    if reconciliation.get("reconciliation_id") != EXPECTED_RECONCILIATION_ID:
        raise ValueError("Unexpected reconciliation ID")
    if reconciliation.get("status") != "RECONCILIATION_COMPLETE_OWNER_ACCEPTANCE_REQUIRED":
        raise ValueError("Unexpected reconciliation status")

    registered_outputs = [
        item for item in registry.get("outputs", []) if item.get("role") == "reconciliation"
    ]
    if len(registered_outputs) != 1:
        raise ValueError("Registry must contain exactly one reconciliation output")
    registered = registered_outputs[0]
    if Path(str(registered.get("path"))) != reconciliation_path:
        raise ValueError("Registry and acceptance reference different reconciliation artifacts")
    if registered.get("sha256") != sha256_file(reconciliation_path):
        raise ValueError("Registry reconciliation hash does not match")

    source_rows = reconciliation.get("records", [])
    if len(source_rows) != scope["expected_records"]:
        raise ValueError("Unexpected reconciliation population")
    candidate_ids = [row.get("candidate_id") for row in source_rows]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("Duplicate candidate IDs")
    recommendations = Counter(row.get("reconciled_recommendation") for row in source_rows)
    if dict(sorted(recommendations.items())) != scope["expected_recommendations"]:
        raise ValueError(f"Unexpected recommendation counts: {dict(recommendations)}")

    records = []
    for source in sorted(source_rows, key=lambda row: row["candidate_id"]):
        recommendation = source["reconciled_recommendation"]
        decisive = recommendation in DECISIVE_LABELS
        records.append(
            {
                "candidate_id": source["candidate_id"],
                "blind_id": source["blind_id"],
                "owner_decision": "ACCEPT_RECONCILED_RECOMMENDATION",
                "reconciled_recommendation": recommendation,
                "ground_truth_status": recommendation if decisive else "UNCERTAIN",
                "ground_truth_materialized": decisive,
                "review_status": "RECONCILED_OWNER_ACCEPTED",
                "training_eligible": "NO",
                "training_exclusion_reason": (
                    "OPENED_EXTERNAL_SCHEMA_REVIEW_PILOT_DIAGNOSTIC_ONLY_AND_DEVELOPMENT_CORPUS_GATE_NOT_MET"
                    if decisive
                    else "UNCERTAIN_EXCLUDED_FROM_BINARY_TASK"
                ),
            }
        )

    ground_truth_counts = Counter(row["ground_truth_status"] for row in records)
    materialized_count = sum(row["ground_truth_materialized"] for row in records)
    return {
        "artifact_id": "ISI_TARGET_TEXT_CORPUS_V1_OWNER_ACCEPTED_GROUND_TRUTH_V1",
        "status": "OWNER_ACCEPTED_15_DECISIVE_LABELS_7_UNCERTAIN_TRAINING_CLOSED",
        "created_at": acceptance["accepted_at"],
        "inputs": {
            "owner_acceptance": {
                "path": str(acceptance_path),
                "sha256": sha256_file(acceptance_path),
            },
            "reconciliation_registry": {
                "path": str(registry_path),
                "sha256": sha256_file(registry_path),
            },
            "reconciliation_artifact": {
                "path": str(reconciliation_path),
                "sha256": sha256_file(reconciliation_path),
            },
        },
        "acceptance_basis": {
            "adopter_role": acceptance["adopter_role"],
            "authorization_source": acceptance["authorization_source"],
            "independent_human_evidence_rereview_claimed": contract[
                "independent_human_evidence_rereview_claimed"
            ],
        },
        "records": records,
        "summary": {
            "reviewed_records": len(records),
            "ground_truth_counts": dict(sorted(ground_truth_counts.items())),
            "decisive_labels_materialized": materialized_count,
            "uncertain_records_retained": ground_truth_counts["UNCERTAIN"],
            "training_eligible_records": 0,
        },
        "decision": {
            "owner_acceptance_complete": True,
            "ground_truth_labeling_completed_for_decisive_pilot_records": True,
            "diagnostic_only": True,
            "development_corpus_gate_met": False,
            "training_allowed": False,
            "next_gate": "Freeze the Dataset V1-Core sampling matrix and source quotas before acquiring a fresh development cohort.",
        },
        "safety_contract": {
            "raw_records_changed": 0,
            "model_fit_operations": 0,
            "model_scoring_operations": 0,
            "validation_or_test_openings": 0,
            "training_allowed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acceptance", type=Path, required=True)
    args = parser.parse_args()
    acceptance = load_object(args.acceptance)
    output = Path(str(acceptance["outputs"]["accepted_ground_truth"]))
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {output}")
    result = materialize(args.acceptance)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(
        json.dumps(
            {"output": str(output), "sha256": sha256_file(output), "summary": result["summary"]},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
