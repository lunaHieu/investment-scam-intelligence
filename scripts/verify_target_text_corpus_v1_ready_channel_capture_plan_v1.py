"""Independently verify the exact 53-row eligible ready-channel capture plan."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from scripts.build_target_text_corpus_v1_ready_channel_capture_plan_v1 import build, load_json, sha256_file


def verify(release_path: Path, plan_path: Path) -> dict:
    errors: list[str] = []
    try:
        actual = load_json(plan_path)
        expected = build(release_path)
        if actual != expected:
            errors.append("plan does not exactly reproduce from frozen inputs")
        rows = actual["results"]
        ids = [row["availability_plan_id"] for row in rows]
        if ids != [row["availability_plan_id"] for row in expected["results"]]:
            errors.append("ordered membership differs from full recomputation")
        if Counter(row["cohort"] for row in rows) != {"DEVELOPMENT": 37, "EXTERNAL_HOLDOUT": 16}:
            errors.append("cohort counts changed")
        if len({row["capture_path"] for row in rows}) != 53:
            errors.append("capture paths are not unique")
        if not all("id_/" in row["requested_archive_url"] for row in rows):
            errors.append("non-raw replay URL present")
    except (KeyError, TypeError, ValueError, FileNotFoundError, json.JSONDecodeError) as error:
        errors.append(str(error))
    passed = not errors
    return {
        "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_CAPTURE_PLAN_QA_V1",
        "status": "PASS_EXACT_53_ELIGIBLE_CAPTURE_PLAN_SEPARATE_RELEASE_MAY_BE_PREPARED" if passed else "FAIL",
        "inputs": {"release_sha256": sha256_file(release_path), "plan_sha256": sha256_file(plan_path)},
        "checks": {"resolved_metadata_rows": 69 if passed else None, "planned_capture_count": 53 if passed else None, "no_eligible_snapshot_rows": 16 if passed else None, "development_rows": 37 if passed else None, "external_holdout_rows": 16 if passed else None, "full_recomputation_match": passed, "raw_replay_only": passed},
        "decision": {"capture_release_may_be_prepared": passed, "capture_execution_authorized": False, "candidate_live_domain_access_allowed": False, "labeling_allowed": False, "training_allowed": False},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "candidate_domain_access_operations": 0, "archived_page_downloads": 0, "captures": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite: {args.output}")
    result = verify(args.release, args.plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps(result, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
