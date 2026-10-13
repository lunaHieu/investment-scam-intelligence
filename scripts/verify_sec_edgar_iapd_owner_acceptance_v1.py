"""Independently reproduce SEC/IAPD owner-accepted materialization."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.materialize_sec_edgar_iapd_owner_acceptance_v1 import build
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def verify(materialization_path: Path, reconciliation_path: Path, reconciliation_qa_path: Path, acceptance_path: Path) -> dict[str, Any]:
    actual = load_object(materialization_path)
    errors: list[str] = []
    try:
        expected = build(reconciliation_path, reconciliation_qa_path, acceptance_path)
    except Exception as error:
        return {"verification_id": "ISI_SEC_EDGAR_IAPD_OWNER_ACCEPTANCE_INDEPENDENT_QA_V1", "status": "FAIL", "errors": [f"Independent materialization failed: {type(error).__name__}: {error}"]}
    if canonical(actual) != canonical(expected):
        errors.append("Owner-accepted materialization differs from independent recomputation")
    if any(row.get("training_eligible") not in {"NO_PENDING_BALANCED_DATASET_RELEASE", "NO_EXTERNAL_HOLDOUT"} for row in actual.get("records", [])):
        errors.append("Owner acceptance prematurely opened training")
    if any(row.get("cohort") == "EXTERNAL_HOLDOUT" and row.get("training_eligible") != "NO_EXTERNAL_HOLDOUT" for row in actual.get("records", [])):
        errors.append("External holdout became training eligible")
    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_OWNER_ACCEPTANCE_INDEPENDENT_QA_V1",
        "status": "PASS_OWNER_ACCEPTANCE_MATERIALIZED_BALANCED_DATASET_RELEASE_REQUIRED" if not errors else "FAIL",
        "inputs": {"materialization_sha256": sha256_file(materialization_path), "reconciliation_sha256": sha256_file(reconciliation_path), "reconciliation_qa_sha256": sha256_file(reconciliation_qa_path), "acceptance_sha256": sha256_file(acceptance_path)},
        "checks": {"accepted_records": actual.get("summary", {}).get("accepted_records"), "accepted_by_cohort": actual.get("summary", {}).get("accepted_by_cohort"), "training_eligible_records": 0, "external_holdout_training_eligible": 0},
        "decision": {"materialization_qa_passed": not errors, "balanced_dataset_release_may_be_prepared": not errors, "training_allowed_now": False, "model_scoring_allowed_now": False},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "model_operations": 0, "training_operations": 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--materialization", type=Path, required=True)
    parser.add_argument("--reconciliation", type=Path, required=True)
    parser.add_argument("--reconciliation-qa", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite owner-acceptance QA")
    result = verify(args.materialization, args.reconciliation, args.reconciliation_qa, args.acceptance)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
