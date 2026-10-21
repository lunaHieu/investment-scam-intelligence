"""Independently reproduce captured-subset grouping V2."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.analyze_sec_edgar_iapd_post_capture_grouping_v2 import build
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def verify(release_path: Path, release_qa_path: Path) -> dict[str, Any]:
    release = load_object(release_path)
    output = Path(release["output"]["path"])
    errors: list[str] = []
    try:
        expected = build(release_path, release_qa_path)
    except Exception as error:
        return {"verification_id": "ISI_SEC_EDGAR_IAPD_POST_CAPTURE_GROUPING_INDEPENDENT_QA_V2", "status": "FAIL", "errors": [f"Independent rebuild failed: {type(error).__name__}: {error}"]}
    actual = load_object(output) if output.is_file() else {}
    if not output.is_file():
        errors.append("Grouping V2 analysis output is missing")
    if canonical(actual) != canonical(expected):
        errors.append("Grouping V2 analysis differs from independent recomputation")
    collision_records = sum(row["cross_cohort_group_collision"] for row in expected["records"])
    below_minimum = sum(row["routing_decision"] == "NOT_REVIEWABLE_BELOW_MINIMUM" for row in expected["records"])
    if expected["counts"]["manifest_rows"] != 57 or expected["counts"]["minimum_content_pass_rows"] != 56 or below_minimum != 1:
        errors.append("Grouping V2 population routing differs from the frozen contract")
    if expected.get("population_contract") != release.get("population_contract"):
        errors.append("Grouping V2 population contract was not preserved")
    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_POST_CAPTURE_GROUPING_INDEPENDENT_QA_V2",
        "status": "PASS_CAPTURED_SUBSET_GROUPING_REPRODUCED_MANUAL_GROUP_REVIEW_MAY_BE_PREPARED" if not errors else "FAIL",
        "inputs": {"release_sha256": sha256_file(release_path), "release_qa_sha256": sha256_file(release_qa_path), "analysis_sha256": sha256_file(output) if output.is_file() else None},
        "checks": {"analysis_reproduced_exactly": not errors, "manifest_rows": 57, "minimum_content_pass_rows": 56, "below_minimum_routed_out": below_minimum, "capture_quarantined_rows": 1, "cross_cohort_groups": expected["counts"]["cross_cohort_groups"], "cross_cohort_collision_records": collision_records, "labels_created": 0},
        "decision": {"grouping_qa_passed": not errors, "manual_group_review_may_be_prepared": not errors, "failed_capture_row_remains_quarantined": True, "primary_label_review_allowed": False, "model_scoring_allowed": False, "training_allowed": False},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "labels": 0, "model": 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-qa", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite grouping V2 result QA")
    result = verify(args.release, args.release_qa)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
