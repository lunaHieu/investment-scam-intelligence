"""Verify the materialized V1-Core train-only dataset and audit report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.build_target_text_corpus_v1_group_split_plan_v1 import canonical
from scripts.materialize_target_text_corpus_v1_train_only_v1 import dataset_bytes, materialize
from scripts.verify_target_text_corpus_v1_core_release_v1 import load_object, sha256_file


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"Expected object at JSONL line {line_number}")
            rows.append(value)
    return rows


def verify(dataset_path: Path, report_path: Path, release_path: Path, release_qa_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        actual_rows = load_jsonl(dataset_path)
        actual_report = load_object(report_path)
        expected_rows, expected_report, expected_payload = materialize(release_path, release_qa_path)
    except Exception as error:
        return {
            "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_TRAIN_ONLY_RESULT_QA_V1",
            "status": "FAIL",
            "errors": [f"Independent train-only reconstruction failed: {type(error).__name__}: {error}"],
        }
    if canonical(actual_rows) != canonical(expected_rows) or dataset_path.read_bytes() != expected_payload:
        errors.append("Train-only dataset differs from byte-exact independent reconstruction")
    if canonical(actual_report) != canonical(expected_report):
        errors.append("Train-only report differs from independent reconstruction")
    if any(set(row) != {"record_id", "text_content", "label", "group_id"} for row in actual_rows):
        errors.append("Train-only dataset exposes fields outside the frozen schema")
    if len(actual_rows) != 168:
        errors.append("Train-only dataset does not contain exactly 168 records")
    return {
        "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_TRAIN_ONLY_RESULT_QA_V1",
        "status": "PASS_TRAIN_ONLY_DATASET_REPRODUCED_MODEL_PROTOCOL_REQUIRED" if not errors else "FAIL",
        "inputs": {
            "dataset_sha256": sha256_file(dataset_path),
            "report_sha256": sha256_file(report_path),
            "release_sha256": sha256_file(release_path),
            "release_qa_sha256": sha256_file(release_qa_path),
        },
        "checks": {
            "record_count": len(actual_rows),
            "dataset_fields": ["group_id", "label", "record_id", "text_content"],
            "validation_records": 0,
            "internal_test_records": 0,
            "external_holdout_records": 0,
        },
        "decision": {
            "train_only_result_qa_passed": not errors,
            "model_development_protocol_may_be_prepared": not errors,
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
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-qa", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite train-only result QA")
    result = verify(args.dataset, args.report, args.release, args.release_qa)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
