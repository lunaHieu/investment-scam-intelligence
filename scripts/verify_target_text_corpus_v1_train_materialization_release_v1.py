"""Independently reproduce a V1-Core train-only materialization release."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.build_target_text_corpus_v1_group_split_plan_v1 import canonical
from scripts.build_target_text_corpus_v1_train_materialization_release_v1 import build
from scripts.verify_target_text_corpus_v1_core_release_v1 import load_object, sha256_file


def verify(release_path: Path, *, require_outputs_absent: bool = True) -> dict[str, Any]:
    actual = load_object(release_path)
    inputs = actual.get("inputs", {})
    outputs = actual.get("outputs", {})
    errors: list[str] = []
    try:
        contract_path = Path(inputs["contract"]["path"])
        split_plan_path = Path(inputs["split_plan"]["path"])
        split_qa_path = Path(inputs["split_qa"]["path"])
        if inputs["contract"]["sha256"] != sha256_file(contract_path):
            raise ValueError("Train-materialization contract binding mismatch")
        if inputs["split_plan"]["sha256"] != sha256_file(split_plan_path):
            raise ValueError("Split-plan binding mismatch")
        if inputs["split_qa"]["sha256"] != sha256_file(split_qa_path):
            raise ValueError("Split-QA binding mismatch")
        expected = build(
            contract_path,
            split_plan_path,
            split_qa_path,
            Path(outputs["dataset"]),
            Path(outputs["report"]),
            str(actual["created_at"]),
            require_outputs_absent=require_outputs_absent,
        )
    except Exception as error:
        return {
            "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_TRAIN_MATERIALIZATION_RELEASE_QA_V1",
            "status": "FAIL",
            "errors": [f"Independent release reconstruction failed: {type(error).__name__}: {error}"],
        }
    if canonical(actual) != canonical(expected):
        errors.append("Train-materialization release differs from independent recomputation")
    records = list(actual.get("records", []))
    if len(records) != 168 or any(row.get("label") not in {0, 1} for row in records):
        errors.append("Train release record count or label mapping is invalid")
    if actual.get("summary", {}).get("validation_records") != 0 or actual.get("summary", {}).get("internal_test_records") != 0 or actual.get("summary", {}).get("external_holdout_records") != 0:
        errors.append("Train release includes a forbidden partition")
    return {
        "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_TRAIN_MATERIALIZATION_RELEASE_QA_V1",
        "status": "PASS_TRAIN_ONLY_RELEASE_REPRODUCED_EXECUTION_MAY_PROCEED" if not errors else "FAIL",
        "inputs": {"release_sha256": sha256_file(release_path)},
        "checks": {
            "train_records": len(records),
            "validation_records": 0,
            "internal_test_records": 0,
            "external_holdout_records": 0,
        },
        "decision": {
            "release_qa_passed": not errors,
            "materialization_execution_allowed": not errors,
            "training_allowed_now": False,
            "validation_opening_allowed": False,
            "internal_test_opening_allowed": False,
            "external_holdout_opening_allowed": False,
        },
        "errors": errors,
        "safety_contract": {"network_operations": 0, "model_operations": 0, "training_operations": 0, "validation_or_test_openings": 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite train-materialization release QA")
    result = verify(args.release)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
