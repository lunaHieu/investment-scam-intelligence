"""Build a deterministic, metadata-only group split for validated Dataset V1-Core."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_core_release_v1 import (
    load_object,
    resolve,
    sha256_file,
    verify as verify_core_release,
)


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def build(contract_path: Path, manifest_path: Path, release_qa_path: Path) -> dict[str, Any]:
    contract = load_object(contract_path)
    manifest = load_object(manifest_path)
    release_qa = load_object(release_qa_path)
    root = contract_path.resolve().parents[1]
    if contract.get("contract_id") != "ISI_TARGET_TEXT_CORPUS_V1_GROUP_SPLIT_CONTRACT_V1":
        raise ValueError("Unexpected group-split contract")
    if any(contract.get("decision", {}).values()):
        raise ValueError("Group-split contract prematurely opens a data or model gate")

    core_ref = contract["core_release_contract"]
    core_contract_path = resolve(root, core_ref["path"])
    if not core_contract_path.is_file() or sha256_file(core_contract_path) != core_ref["sha256"]:
        raise ValueError("Core-release contract path or hash mismatch")
    expected_qa = verify_core_release(core_contract_path, manifest_path)
    if canonical(release_qa) != canonical(expected_qa):
        raise ValueError("Core-release QA differs from independent recomputation")
    if release_qa.get("status") != contract["required_core_release_qa_status"]:
        raise ValueError("Core-release QA did not release split planning")
    if release_qa.get("inputs", {}).get("manifest_sha256") != sha256_file(manifest_path):
        raise ValueError("Core-release QA binding mismatch")
    if release_qa.get("decision", {}).get("development_group_split_plan_may_be_prepared") is not True:
        raise ValueError("Core-release QA kept split planning closed")

    records = list(manifest.get("records", []))
    development = [row for row in records if row.get("cohort") == "DEVELOPMENT"]
    holdout = [row for row in records if row.get("cohort") == "EXTERNAL_HOLDOUT"]
    totals = contract["expected_totals"]
    if len(development) != totals["development"] or len(holdout) != totals["external_holdout_sealed"]:
        raise ValueError("Core release population differs from the split contract")

    seed = contract["frozen_seed"]
    quotas = contract["partition_quota_per_target_channel"]
    strata: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in development:
        strata[(str(row["target_status"]), str(row["channel_id"]))].append(row)

    assignments: list[dict[str, Any]] = []
    for (target_status, channel_id), rows in sorted(strata.items()):
        ranked = []
        for row in rows:
            key_material = "|".join((seed, "DEVELOPMENT", target_status, channel_id, str(row["record_id"]), str(row["transitive_group_id"])))
            ranked.append((hashlib.sha256(key_material.encode("utf-8")).hexdigest(), row))
        ranked.sort(key=lambda item: (item[0], str(item[1]["record_id"])))
        if len(ranked) != sum(quotas.values()):
            raise ValueError(f"Unexpected stratum size: {target_status}/{channel_id}")
        boundaries = (
            ("train", 0, quotas["train"]),
            ("validation", quotas["train"], quotas["train"] + quotas["validation"]),
            ("internal_test", quotas["train"] + quotas["validation"], sum(quotas.values())),
        )
        for partition, start, stop in boundaries:
            for rank, (key, row) in enumerate(ranked[start:stop], start=start + 1):
                assignments.append({
                    "record_id": row["record_id"],
                    "target_status": target_status,
                    "channel_id": channel_id,
                    "cohort": "DEVELOPMENT",
                    "partition": partition,
                    "transitive_group_id": row["transitive_group_id"],
                    "selection_rank_within_stratum": rank,
                    "deterministic_key_sha256": key,
                    "record_commitment_sha256": sha256_value(row),
                })

    allowed_fields = set(contract["assignment_output_fields"])
    if any(set(row) != allowed_fields for row in assignments):
        raise ValueError("Split assignment schema differs from the frozen contract")
    forbidden = set(contract["forbidden_assignment_fields"])
    if any(forbidden.intersection(row) for row in assignments):
        raise ValueError("Split plan exposes a forbidden source or model field")
    assignment_ids = [str(row["record_id"]) for row in assignments]
    if len(assignment_ids) != len(set(assignment_ids)) or set(assignment_ids) != {str(row["record_id"]) for row in development}:
        raise ValueError("Development assignment population mismatch")
    partition_counts = Counter(str(row["partition"]) for row in assignments)
    if dict(partition_counts) != {key: totals[key] for key in ("train", "validation", "internal_test")}:
        raise ValueError("Partition totals differ from the frozen contract")

    holdout_commitments = sorted(
        (str(row["record_id"]), sha256_value(row))
        for row in holdout
    )
    return {
        "split_plan_id": contract["split_namespace"],
        "status": "FROZEN_METADATA_ONLY_ASSIGNMENTS_MATERIALIZATION_RELEASE_REQUIRED",
        "inputs": {
            "contract": {"path": str(contract_path.resolve()), "sha256": sha256_file(contract_path)},
            "core_release_manifest": {"path": str(manifest_path.resolve()), "sha256": sha256_file(manifest_path)},
            "core_release_qa": {"path": str(release_qa_path.resolve()), "sha256": sha256_file(release_qa_path)},
        },
        "method": {
            "unit_of_assignment": contract["unit_of_assignment"],
            "stratification_fields": contract["stratification_fields"],
            "deterministic_key": contract["deterministic_key"],
            "frozen_seed_sha256": hashlib.sha256(seed.encode("utf-8")).hexdigest(),
            "text_or_model_signal_used": False,
        },
        "development_assignments": assignments,
        "external_holdout_seal": {
            "record_count": len(holdout),
            "population_commitment_sha256": sha256_value(holdout_commitments),
            "record_ids_exposed": False,
            "training_use_allowed": False,
            "model_selection_use_allowed": False,
            "scoring_allowed_now": False,
        },
        "summary": {
            "development_records": len(assignments),
            "partition_counts": dict(sorted(partition_counts.items())),
            "external_holdout_records_sealed": len(holdout),
            "text_fields_exposed": 0,
            "model_signals_used": 0,
        },
        "decision": {
            "assignments_frozen": True,
            "train_materialization_release_required": True,
            "train_materialization_allowed_now": False,
            "validation_opening_allowed": False,
            "internal_test_opening_allowed": False,
            "external_holdout_opening_allowed": False,
            "training_allowed": False,
        },
        "safety_contract": {
            "network_operations": 0,
            "model_operations": 0,
            "training_operations": 0,
            "validation_or_test_openings": 0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--release-qa", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite group-split plan")
    result = build(args.contract, args.manifest, args.release_qa)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({"split_plan_id": result["split_plan_id"], "summary": result["summary"], "output": str(args.output), "sha256": sha256_file(args.output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
