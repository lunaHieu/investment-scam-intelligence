"""Freeze a balanced Wayback holdout V3 capture plan from clean availability."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_balanced_wayback_capture_plan_v2 import BRANCHES, select_balanced
from src.isi.normalization.external_references import sha256_file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--availability-report", type=Path, required=True)
    parser.add_argument("--availability-sha256", required=True)
    parser.add_argument("--per-branch", type=int, required=True)
    parser.add_argument("--seed", default="20261002-wayback-holdout-v3-capture")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {args.output}")
    if sha256_file(args.availability_report) != args.availability_sha256:
        raise ValueError("Availability report SHA-256 mismatch")
    source = json.loads(args.availability_report.read_text(encoding="utf-8-sig"))
    if source.get("report_id") != "WAYBACK_HOLDOUT_AVAILABILITY_V3":
        raise ValueError("Unexpected availability report")
    if source.get("unresolved_error_count") != 0 or source.get("acquisition_ready") is not True:
        raise ValueError("Availability errors must be resolved before planning")
    selected, counts = select_balanced(
        source["results"], per_branch=args.per_branch, seed=args.seed
    )
    available_counts = {
        branch: sum(
            row.get("available") is True and row.get("reference_branch") == branch
            for row in source["results"]
        )
        for branch in BRANCHES
    }
    report = {
        "report_id": "WAYBACK_HOLDOUT_BALANCED_CAPTURE_PLAN_V3",
        "created_at": "2026-10-02",
        "status": "FROZEN_BALANCED_CAPTURE_PLAN_UNLABELED",
        "availability_report": str(args.availability_report),
        "availability_report_sha256": args.availability_sha256,
        "queue_path": source["queue_path"],
        "queue_sha256": source["queue_sha256"],
        "selection_seed": args.seed,
        "requested_candidate_count": len(selected),
        "requested_by_reference_branch": counts,
        "available_pool_by_reference_branch": available_counts,
        "reserve_available_by_reference_branch": {
            branch: available_counts[branch] - counts[branch] for branch in BRANCHES
        },
        "unresolved_error_count": 0,
        "results": selected,
        "safety_contract": {
            "network_operations": 0,
            "candidate_live_domain_access_operations": 0,
            "labels_created": 0,
            "model_scoring_operations": 0,
            "training_allowed": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "status": "OK",
        "output": str(args.output),
        "sha256": sha256_file(args.output),
        "selected_by_reference_branch": counts,
        "reserve_available_by_reference_branch": report["reserve_available_by_reference_branch"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
