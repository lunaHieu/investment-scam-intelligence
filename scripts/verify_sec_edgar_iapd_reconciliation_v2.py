"""Independently reproduce captured-subset reconciliation V2."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.reconcile_sec_edgar_iapd_reviews_v2 import build
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def verify(reconciliation_path: Path) -> dict[str, Any]:
    actual = load_object(reconciliation_path)
    inputs = actual.get("inputs", {})
    errors: list[str] = []
    try:
        expected = build(Path(inputs["primary_review"]["path"]), Path(inputs["primary_qa"]["path"]), Path(inputs["blind_second_review"]["path"]), Path(inputs["blind_second_qa"]["path"]))
    except Exception as error:
        return {"verification_id": "ISI_SEC_EDGAR_IAPD_RECONCILIATION_INDEPENDENT_QA_V2", "status": "FAIL", "errors": [f"Independent reconciliation failed: {type(error).__name__}: {error}"]}
    if canonical(actual) != canonical(expected):
        errors.append("Reconciliation V2 differs from conservative independent recomputation")
    contract = actual.get("population_contract", {})
    if contract.get("reconciled_rows") != 56 or contract.get("below_minimum_rows") != 1 or contract.get("capture_quarantined_rows") != 1:
        errors.append("Reconciliation V2 population/quarantine contract changed")
    if any(row.get("label_created") is not False or row.get("ground_truth_status") != "UNCERTAIN" or row.get("owner_acceptance") != "PENDING" for row in actual.get("records", [])):
        errors.append("Reconciliation prematurely created a label or owner acceptance")
    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_RECONCILIATION_INDEPENDENT_QA_V2",
        "status": "PASS_CAPTURED_SUBSET_RECONCILIATION_REPRODUCED_OWNER_ACCEPTANCE_REQUIRED" if not errors else "FAIL",
        "inputs": {"reconciliation_sha256": sha256_file(reconciliation_path)},
        "checks": {"record_count": actual.get("summary", {}).get("record_count"), "review_disagreements": actual.get("summary", {}).get("review_disagreements"), "owner_acceptance_pending": actual.get("summary", {}).get("owner_acceptance_pending"), "capture_quarantined_rows": 1, "below_minimum_rows": 1, "labels_created": 0},
        "decision": {"reconciliation_qa_passed": not errors, "owner_acceptance_required": True, "materialization_allowed_now": False, "training_allowed": False},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "labels": 0, "model": 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reconciliation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite reconciliation V2 QA")
    result = verify(args.reconciliation)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
