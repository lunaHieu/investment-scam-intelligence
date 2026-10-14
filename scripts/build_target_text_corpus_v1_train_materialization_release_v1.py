"""Build a frozen release for materializing only V1-Core train assignments."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.build_target_text_corpus_v1_group_split_plan_v1 import canonical
from scripts.verify_target_text_corpus_v1_core_release_v1 import load_object, resolve, sha256_file
from scripts.verify_target_text_corpus_v1_group_split_plan_v1 import verify as verify_split


def validate_timestamp(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("created_at must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError("created_at must include a timezone")


def validate_outputs(contract: dict[str, Any], dataset_output: Path, report_output: Path, *, require_absent: bool) -> None:
    dataset = dataset_output.resolve()
    report = report_output.resolve()
    output_contract = contract["output_contract"]
    if dataset == report or (output_contract["same_parent_directory_required"] and dataset.parent != report.parent):
        raise ValueError("Dataset and report outputs must be distinct siblings")
    if dataset.suffix != output_contract["dataset_suffix"] or report.suffix != output_contract["report_suffix"]:
        raise ValueError("Dataset or report output suffix differs from the contract")
    for path in (dataset, report):
        if require_absent and (path.exists() or path.with_suffix(path.suffix + ".partial").exists()):
            raise FileExistsError(f"Refusing to overwrite train materialization output: {path}")


def build(
    contract_path: Path,
    split_plan_path: Path,
    split_qa_path: Path,
    dataset_output: Path,
    report_output: Path,
    created_at: str,
    *,
    require_outputs_absent: bool = True,
) -> dict[str, Any]:
    contract = load_object(contract_path)
    split_plan = load_object(split_plan_path)
    split_qa = load_object(split_qa_path)
    root = contract_path.resolve().parents[1]
    if contract.get("contract_id") != "ISI_TARGET_TEXT_CORPUS_V1_TRAIN_MATERIALIZATION_CONTRACT_V1":
        raise ValueError("Unexpected train-materialization contract")
    if any(contract.get("decision", {}).values()):
        raise ValueError("Train-materialization contract prematurely opens a data or model gate")
    validate_timestamp(created_at)
    validate_outputs(contract, dataset_output, report_output, require_absent=require_outputs_absent)

    split_contract_ref = contract["group_split_contract"]
    split_contract_path = resolve(root, split_contract_ref["path"])
    if not split_contract_path.is_file() or sha256_file(split_contract_path) != split_contract_ref["sha256"]:
        raise ValueError("Group-split contract path or hash mismatch")
    if split_plan.get("inputs", {}).get("contract", {}).get("sha256") != sha256_file(split_contract_path):
        raise ValueError("Split plan is not bound to the frozen split contract")
    expected_split_qa = verify_split(split_plan_path)
    if canonical(split_qa) != canonical(expected_split_qa):
        raise ValueError("Split QA differs from independent recomputation")
    if split_qa.get("status") != contract["required_split_qa_status"]:
        raise ValueError("Split QA did not release train-materialization planning")
    if split_qa.get("inputs", {}).get("split_plan_sha256") != sha256_file(split_plan_path):
        raise ValueError("Split QA binding mismatch")
    if split_qa.get("decision", {}).get("train_materialization_release_may_be_prepared") is not True:
        raise ValueError("Split QA kept train materialization closed")

    train_assignments = [row for row in split_plan.get("development_assignments", []) if row.get("partition") == "train"]
    if len(train_assignments) != contract["expected_train_records"]:
        raise ValueError("Train assignment count differs from the frozen contract")
    if any(row.get("cohort") != "DEVELOPMENT" for row in train_assignments):
        raise ValueError("Non-development record appeared in train release")
    if any(row.get("partition") in contract["forbidden_partitions"] for row in train_assignments):
        raise ValueError("Forbidden partition appeared in train release")
    label_counts = Counter(str(row["target_status"]) for row in train_assignments)
    if dict(label_counts) != contract["expected_records_per_label"]:
        raise ValueError("Train label counts differ from the frozen contract")
    channel_counts = Counter(str(row["channel_id"]) for row in train_assignments)
    if any(value != contract["expected_records_per_channel"] for value in channel_counts.values()) or len(channel_counts) != 4:
        raise ValueError("Train channel counts differ from the frozen contract")

    records = [{
        "record_id": row["record_id"],
        "target_status": row["target_status"],
        "label": contract["label_mapping"][row["target_status"]],
        "channel_id": row["channel_id"],
        "group_id": row["transitive_group_id"],
        "record_commitment_sha256": row["record_commitment_sha256"],
    } for row in train_assignments]
    return {
        "release_id": contract["release_id"],
        "created_at": created_at,
        "status": contract["release_status"],
        "inputs": {
            "contract": {"path": str(contract_path.resolve()), "sha256": sha256_file(contract_path)},
            "split_plan": {"path": str(split_plan_path.resolve()), "sha256": sha256_file(split_plan_path)},
            "split_qa": {"path": str(split_qa_path.resolve()), "sha256": sha256_file(split_qa_path)},
            "core_release_manifest": split_plan["inputs"]["core_release_manifest"],
        },
        "outputs": {
            "dataset": str(dataset_output.resolve()),
            "report": str(report_output.resolve()),
        },
        "records": records,
        "summary": {
            "record_count": len(records),
            "label_counts": dict(sorted(label_counts.items())),
            "channel_counts": dict(sorted(channel_counts.items())),
            "validation_records": 0,
            "internal_test_records": 0,
            "external_holdout_records": 0,
        },
        "decision": {
            "independent_release_qa_required": True,
            "execution_allowed_now": False,
            "training_allowed": False,
            "validation_opening_allowed": False,
            "internal_test_opening_allowed": False,
            "external_holdout_opening_allowed": False,
        },
        "safety_contract": {"network_operations": 0, "model_operations": 0, "training_operations": 0, "validation_or_test_openings": 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--split-plan", type=Path, required=True)
    parser.add_argument("--split-qa", type=Path, required=True)
    parser.add_argument("--dataset-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite train-materialization release")
    result = build(args.contract, args.split_plan, args.split_qa, args.dataset_output, args.report_output, args.created_at)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({"release_id": result["release_id"], "summary": result["summary"], "output": str(args.output), "sha256": sha256_file(args.output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
