"""Build the exact-48 never-attempted ready-channel capture continuation plan."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.build_target_text_corpus_v1_ready_channel_capture_continuation_plan_v1 import load, sha256_file


def build(parent_plan_path: Path, report_path: Path, result_qa_path: Path) -> dict[str, Any]:
    parent, report, qa = load(parent_plan_path), load(report_path), load(result_qa_path)
    if parent.get("status") != "FROZEN_EXACT_49_NEVER_ATTEMPTED_ONLY_CAPTURE_PLAN":
        raise ValueError("parent continuation plan changed")
    if (
        report.get("status") != "INCOMPLETE_FAILURES_PRESERVED"
        or report.get("captured_count") != 0
        or report.get("failed_count") != 1
        or report.get("not_attempted_count") != 48
    ):
        raise ValueError("parent continuation result is not the exact frozen partial state")
    if qa.get("status") != "PASS_PARTIAL_CONTINUATION_PRESERVED":
        raise ValueError("parent continuation result QA did not pass")
    if qa.get("inputs", {}).get("report_sha256") != sha256_file(report_path):
        raise ValueError("parent continuation report/QA hash mismatch")
    parent_by_id = {row["capture_plan_id"]: row for row in parent["results"]}
    rows = [
        parent_by_id[row["capture_plan_id"]]
        for row in report["results"]
        if row["outcome"] == "NOT_ATTEMPTED_AFTER_ERROR_STOP"
    ]
    if len(rows) != 48 or any(Path(row["capture_path"]).exists() for row in rows):
        raise ValueError("exact-48 membership changed or target already exists")
    ids = [row["availability_plan_id"] for row in rows]
    forbidden = {
        "TTCV1_B3_AVAIL_002",
        "TTCV1_B3_AVAIL_003",
        "TTCV1_B3_AVAIL_005",
        "TTCV1_B3_AVAIL_009",
        "TTCV1_B3_AVAIL_010",
    }
    if forbidden.intersection(ids):
        raise ValueError("captured or failed row leaked into exact-48 continuation")
    counts = Counter(row["cohort"] for row in rows)
    return {
        "plan_id": "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_CAPTURE_CONTINUATION_PLAN_V2",
        "status": "FROZEN_EXACT_48_NEVER_ATTEMPTED_ONLY_CAPTURE_PLAN",
        "inputs": {
            "parent_plan": {"path": str(parent_plan_path.resolve()), "sha256": sha256_file(parent_plan_path)},
            "parent_report": {"path": str(report_path.resolve()), "sha256": sha256_file(report_path)},
            "parent_result_qa": {"path": str(result_qa_path.resolve()), "sha256": sha256_file(result_qa_path)},
        },
        "planned_capture_count": 48,
        "planned_by_cohort": dict(counts),
        "excluded_captured_rows": ["TTCV1_B3_AVAIL_002", "TTCV1_B3_AVAIL_003", "TTCV1_B3_AVAIL_005"],
        "excluded_quarantined_rows": ["TTCV1_B3_AVAIL_009", "TTCV1_B3_AVAIL_010"],
        "results": rows,
        "decision": {
            "continuation_release_may_be_prepared": False,
            "capture_execution_authorized": False,
            "candidate_live_domain_access_allowed": False,
            "labeling_allowed": False,
            "training_allowed": False,
        },
        "safety_contract": {"network_operations": 0, "new_captures": 0, "labels_created": 0, "model_operations": 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-plan", type=Path, required=True)
    parser.add_argument("--parent-report", type=Path, required=True)
    parser.add_argument("--parent-result-qa", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite: {args.output}")
    plan = build(args.parent_plan, args.parent_report, args.parent_result_qa)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": plan["status"], "planned_capture_count": 48, "sha256": sha256_file(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
