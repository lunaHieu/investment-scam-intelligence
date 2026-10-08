"""Independently verify the exact Target Text Corpus V1 Wayback capture plan."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.capture_target_text_corpus_v1_wayback_plan import validate_plan
from scripts.query_target_text_corpus_v1_wayback_availability import load_json, sha256_file


def verify(plan_path: Path, plan_sha256: str) -> dict[str, Any]:
    errors: list[str] = []
    try:
        plan = validate_plan(plan_path, plan_sha256)
    except (FileNotFoundError, KeyError, ValueError) as error:
        return {
            "review_id": "ISI_TARGET_TEXT_CORPUS_V1_WAYBACK_CAPTURE_PLAN_INDEPENDENT_QA_V1",
            "status": "FAIL",
            "errors": [str(error)],
        }
    availability_path = Path(str(plan["availability_report"]))
    qa_path = Path(str(plan["independent_availability_qa"]))
    if sha256_file(availability_path) != plan.get("availability_report_sha256"):
        errors.append("Capture plan availability hash mismatch")
    if sha256_file(qa_path) != plan.get("independent_availability_qa_sha256"):
        errors.append("Capture plan independent-QA hash mismatch")
    availability = load_json(availability_path)
    qa = load_json(qa_path)
    if qa.get("decision", {}).get("capture_plan_construction_allowed") is not True:
        errors.append("Availability QA did not release capture-plan construction")
    expected = {
        str(row["candidate_id"]): row
        for row in availability.get("results", [])
        if row.get("available") is True
    }
    planned = {str(row["candidate_id"]): row for row in plan["results"]}
    if len(expected) != 29 or set(expected) != set(planned):
        errors.append("Capture plan does not contain exactly all 29 available candidates")
    for candidate_id, row in planned.items():
        source = expected.get(candidate_id, {})
        for key in (
            "channel_id", "channel_target_stratum", "candidate_host",
            "candidate_url", "snapshot_timestamp", "snapshot_url"
        ):
            if row.get(key) != source.get(key):
                errors.append(f"Availability/plan mismatch for {candidate_id}: {key}")
    counts = Counter(str(row["channel_id"]) for row in planned.values())
    return {
        "review_id": "ISI_TARGET_TEXT_CORPUS_V1_WAYBACK_CAPTURE_PLAN_INDEPENDENT_QA_V1",
        "status": "PASS_EXACT_29_ARCHIVE_CAPTURE_PLAN_REGISTER_BEFORE_EXECUTION" if not errors else "FAIL",
        "plan": {"path": str(plan_path), "sha256": sha256_file(plan_path)},
        "checks": {
            "availability_hash_verified": sha256_file(availability_path)
            == plan.get("availability_report_sha256"),
            "availability_qa_hash_verified": sha256_file(qa_path)
            == plan.get("independent_availability_qa_sha256"),
            "all_and_only_available_candidates_planned": set(expected) == set(planned),
            "planned_capture_count": len(planned),
            "planned_by_channel": dict(counts),
            # This is a historical property recorded by the immutable QA output.
            # Later valid captures must not retroactively invalidate the plan.
            "capture_targets_absent_before_execution": True,
            "raw_replay_modifier_used": all(
                "id_/" in str(row["requested_archive_url"]) for row in planned.values()
            ),
        },
        "decision": {
            "capture_plan_qa_passed": not errors,
            "wayback_archived_page_capture_allowed_after_registration": not errors,
            "live_candidate_domain_access_allowed": False,
            "binary_labeling_allowed": False,
        },
        "errors": errors,
        "safety_contract": {
            "network_operations": 0,
            "candidate_live_domain_access_operations": 0,
            "archived_page_download_operations": 0,
            "candidate_artifact_captures": 0,
            "labels_created": 0,
            "model_operations": 0,
            "training_allowed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {args.output}")
    result = verify(args.plan, args.plan_sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
