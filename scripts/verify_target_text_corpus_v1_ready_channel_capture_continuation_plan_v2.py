"""Independently verify the exact-48 continuation capture plan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.build_target_text_corpus_v1_ready_channel_capture_continuation_plan_v1 import load, sha256_file
from scripts.build_target_text_corpus_v1_ready_channel_capture_continuation_plan_v2 import build


def verify(plan_path: Path) -> dict:
    plan = load(plan_path)
    inputs = plan["inputs"]
    expected = build(
        Path(inputs["parent_plan"]["path"]),
        Path(inputs["parent_report"]["path"]),
        Path(inputs["parent_result_qa"]["path"]),
    )
    errors = [] if plan == expected else ["plan does not fully recompute from pinned parent artifacts"]
    ids = [row["availability_plan_id"] for row in plan.get("results", [])]
    if len(ids) != 48 or len(set(ids)) != 48:
        errors.append("exact-48 membership changed")
    if {"TTCV1_B3_AVAIL_009", "TTCV1_B3_AVAIL_010"}.intersection(ids):
        errors.append("quarantined row leaked into exact-48 plan")
    passed = not errors
    return {
        "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_CAPTURE_CONTINUATION_PLAN_QA_V2",
        "status": "PASS_EXACT_48_NEVER_ATTEMPTED_CONTINUATION_PLAN" if passed else "FAIL",
        "plan": {"path": str(plan_path.resolve()), "sha256": sha256_file(plan_path)},
        "checks": {"planned_rows": len(ids), "full_recomputation_match": passed, "quarantined_rows_excluded": passed},
        "decision": {
            "continuation_release_may_be_prepared": passed,
            "capture_execution_authorized": False,
            "candidate_live_domain_access_allowed": False,
            "labeling_allowed": False,
            "training_allowed": False,
        },
        "errors": errors,
        "safety_contract": {"network_operations": 0, "captures": 0, "labels": 0, "model": 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite: {args.output}")
    result = verify(args.plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
