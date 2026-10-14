"""Independently reproduce a Dataset V1-Core deterministic group-split plan."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.build_target_text_corpus_v1_group_split_plan_v1 import build, canonical
from scripts.verify_target_text_corpus_v1_core_release_v1 import load_object, sha256_file


def verify(plan_path: Path) -> dict[str, Any]:
    actual = load_object(plan_path)
    inputs = actual.get("inputs", {})
    errors: list[str] = []
    try:
        contract_path = Path(inputs["contract"]["path"])
        manifest_path = Path(inputs["core_release_manifest"]["path"])
        release_qa_path = Path(inputs["core_release_qa"]["path"])
        if inputs["contract"]["sha256"] != sha256_file(contract_path):
            raise ValueError("Split contract binding mismatch")
        if inputs["core_release_manifest"]["sha256"] != sha256_file(manifest_path):
            raise ValueError("Core-release manifest binding mismatch")
        if inputs["core_release_qa"]["sha256"] != sha256_file(release_qa_path):
            raise ValueError("Core-release QA binding mismatch")
        expected = build(contract_path, manifest_path, release_qa_path)
    except Exception as error:
        return {
            "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_GROUP_SPLIT_INDEPENDENT_QA_V1",
            "status": "FAIL",
            "errors": [f"Independent split reconstruction failed: {type(error).__name__}: {error}"],
        }
    if canonical(actual) != canonical(expected):
        errors.append("Split plan differs from deterministic independent recomputation")
    assignments = list(actual.get("development_assignments", []))
    if any(row.get("cohort") != "DEVELOPMENT" for row in assignments):
        errors.append("Non-development record appeared in model-development assignments")
    forbidden = {"observed_artifact_visible_text", "source_url", "model_score", "model_prediction"}
    if any(forbidden.intersection(row) for row in assignments):
        errors.append("Split plan exposes text, source URL, or model signal")
    counts = Counter(str(row.get("partition")) for row in assignments)
    if counts != Counter({"train": 168, "validation": 36, "internal_test": 36}):
        errors.append("Partition counts differ from 168/36/36")
    holdout = actual.get("external_holdout_seal", {})
    if holdout.get("record_count") != 60 or holdout.get("record_ids_exposed") is not False:
        errors.append("External holdout is not sealed")
    return {
        "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_GROUP_SPLIT_INDEPENDENT_QA_V1",
        "status": "PASS_DETERMINISTIC_SPLIT_REPRODUCED_TRAIN_MATERIALIZATION_RELEASE_REQUIRED" if not errors else "FAIL",
        "inputs": {"split_plan_sha256": sha256_file(plan_path)},
        "checks": {
            "development_assignments": len(assignments),
            "partition_counts": dict(sorted(counts.items())),
            "external_holdout_records_sealed": holdout.get("record_count"),
            "text_fields_exposed": 0,
        },
        "decision": {
            "split_qa_passed": not errors,
            "train_materialization_release_may_be_prepared": not errors,
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
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite group-split QA")
    result = verify(args.plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
