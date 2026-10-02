"""Freeze a balanced capture plan from a complete Wayback availability report."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.normalization.external_references import sha256_file


BRANCHES = ("CONFIRMED_CANDIDATE", "LEGITIMATE_CANDIDATE")


def stable_key(seed: str, row: dict[str, object]) -> str:
    value = f"{seed}|{row['reference_branch']}|{row['candidate_id']}|{row['snapshot_timestamp']}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def select_balanced(
    results: list[dict[str, object]], *, per_branch: int, seed: str
) -> tuple[list[dict[str, object]], dict[str, int]]:
    if per_branch < 1:
        raise ValueError("per_branch must be positive")
    if any(row.get("error") for row in results):
        raise ValueError("Availability errors must be resolved before capture planning")
    available = [row for row in results if row.get("available") is True]
    pools = {
        branch: [row for row in available if row.get("reference_branch") == branch]
        for branch in BRANCHES
    }
    for branch, pool in pools.items():
        if len(pool) < per_branch:
            raise ValueError(f"Insufficient available {branch} rows: {len(pool)} < {per_branch}")
    selected: list[dict[str, object]] = []
    for branch in BRANCHES:
        ranked = sorted(pools[branch], key=lambda row: stable_key(seed, row))
        selected.extend(ranked[:per_branch])
    selected.sort(key=lambda row: str(row["candidate_id"]))
    counts = {branch: sum(row["reference_branch"] == branch for row in selected) for branch in BRANCHES}
    if len({row["candidate_id"] for row in selected}) != len(selected):
        raise ValueError("Balanced plan contains duplicate candidate IDs")
    return selected, counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--availability-report", type=Path, required=True)
    parser.add_argument("--availability-sha256", required=True)
    parser.add_argument("--per-branch", type=int, default=15)
    parser.add_argument("--seed", default="20261001-balanced-capture-v2")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {args.output}")
    if sha256_file(args.availability_report) != args.availability_sha256:
        raise ValueError("Availability report SHA-256 mismatch")
    source = json.loads(args.availability_report.read_text(encoding="utf-8"))
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
        "report_id": "WAYBACK_LANGUAGE_EXPANSION_BALANCED_CAPTURE_PLAN_V2",
        "created_at": "2026-10-01",
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
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "OK",
                "output": str(args.output),
                "sha256": sha256_file(args.output),
                "selected_by_reference_branch": counts,
                "reserve_available_by_reference_branch": report[
                    "reserve_available_by_reference_branch"
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
