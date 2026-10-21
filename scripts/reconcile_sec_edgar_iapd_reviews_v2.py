"""Reconcile captured-subset primary and independent blind reviews."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import scripts.reconcile_sec_edgar_iapd_reviews_v1 as frozen_v1
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


PRIMARY_QA = "PASS_CAPTURED_SUBSET_PRIMARY_REVIEW_BLIND_SECOND_REVIEW_MAY_BE_PREPARED"
SECOND_QA = "PASS_CAPTURED_SUBSET_BLIND_SECOND_REVIEW_RECONCILIATION_MAY_BE_PREPARED"


def build(primary_path: Path, primary_qa_path: Path, second_path: Path, second_qa_path: Path) -> dict[str, Any]:
    original_primary = frozen_v1.PRIMARY_QA
    original_second = frozen_v1.SECOND_QA
    frozen_v1.PRIMARY_QA = PRIMARY_QA
    frozen_v1.SECOND_QA = SECOND_QA
    try:
        result = frozen_v1.build(primary_path, primary_qa_path, second_path, second_qa_path)
    finally:
        frozen_v1.PRIMARY_QA = original_primary
        frozen_v1.SECOND_QA = original_second
    result["reconciliation_id"] = "ISI_SEC_EDGAR_IAPD_RECONCILIATION_V2"
    result["population_contract"] = {
        "source_capture_plan_rows": 58,
        "captured_subset_rows": 57,
        "reconciled_rows": 56,
        "below_minimum_rows": 1,
        "capture_quarantined_rows": 1,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary-review", type=Path, required=True)
    parser.add_argument("--primary-qa", type=Path, required=True)
    parser.add_argument("--second-review", type=Path, required=True)
    parser.add_argument("--second-qa", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite reconciliation V2")
    result = build(args.primary_review, args.primary_qa, args.second_review, args.second_qa)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps({"reconciliation_id": result["reconciliation_id"], "summary": result["summary"], "output": str(args.output), "sha256": sha256_file(args.output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
