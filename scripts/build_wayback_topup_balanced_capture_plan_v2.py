"""Pair confirmed top-up snapshots with untouched legitimate Wayback reserves."""

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


def select_topup_pair(
    confirmed_results: list[dict[str, object]],
    legitimate_results: list[dict[str, object]],
    excluded_candidate_ids: set[str],
    *,
    seed: str,
) -> list[dict[str, object]]:
    if any(row.get("error") for row in [*confirmed_results, *legitimate_results]):
        raise ValueError("All availability errors must be resolved")
    confirmed = [
        row
        for row in confirmed_results
        if row.get("available") is True
        and row.get("reference_branch") == "CONFIRMED_CANDIDATE"
        and row["candidate_id"] not in excluded_candidate_ids
    ]
    legitimate = [
        row
        for row in legitimate_results
        if row.get("available") is True
        and row.get("reference_branch") == "LEGITIMATE_CANDIDATE"
        and row["candidate_id"] not in excluded_candidate_ids
    ]
    if not confirmed:
        raise ValueError("No available confirmed top-up snapshots")
    if len(legitimate) < len(confirmed):
        raise ValueError(f"Insufficient untouched legitimate reserves: {len(legitimate)} < {len(confirmed)}")
    legitimate.sort(
        key=lambda row: hashlib.sha256(
            f"{seed}|{row['candidate_id']}|{row['snapshot_timestamp']}".encode("utf-8")
        ).hexdigest()
    )
    selected = confirmed + legitimate[: len(confirmed)]
    if len({row["candidate_id"] for row in selected}) != len(selected):
        raise ValueError("Top-up capture plan contains duplicate candidate IDs")
    return sorted(selected, key=lambda row: str(row["candidate_id"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirmed-availability", type=Path, required=True)
    parser.add_argument("--confirmed-availability-sha256", required=True)
    parser.add_argument("--legitimate-availability", type=Path, required=True)
    parser.add_argument("--legitimate-availability-sha256", required=True)
    parser.add_argument("--prior-capture-plan", type=Path, required=True)
    parser.add_argument("--prior-capture-plan-sha256", required=True)
    parser.add_argument(
        "--additional-prior-capture-plan",
        nargs=2,
        action="append",
        metavar=("PATH", "SHA256"),
        default=[],
        help="Additional frozen capture plan and SHA-256; may be repeated.",
    )
    parser.add_argument("--seed", default="20261001-wayback-topup-balanced-capture-v2")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {args.output}")
    inputs_to_verify: list[tuple[Path, str]] = [
        (args.confirmed_availability, args.confirmed_availability_sha256),
        (args.legitimate_availability, args.legitimate_availability_sha256),
        (args.prior_capture_plan, args.prior_capture_plan_sha256),
    ]
    additional_prior_plans = [(Path(path), expected) for path, expected in args.additional_prior_capture_plan]
    inputs_to_verify.extend(additional_prior_plans)
    for path, expected in inputs_to_verify:
        if sha256_file(path) != expected:
            raise ValueError(f"Input SHA-256 mismatch: {path}")
    confirmed = json.loads(args.confirmed_availability.read_text(encoding="utf-8"))
    legitimate = json.loads(args.legitimate_availability.read_text(encoding="utf-8"))
    prior_plan_inputs = [(args.prior_capture_plan, args.prior_capture_plan_sha256), *additional_prior_plans]
    excluded: set[str] = set()
    for path, _ in prior_plan_inputs:
        prior_plan = json.loads(path.read_text(encoding="utf-8"))
        excluded.update(str(row["candidate_id"]) for row in prior_plan["results"])
    selected = select_topup_pair(
        confirmed["results"], legitimate["results"], excluded, seed=args.seed
    )
    counts = {
        branch: sum(row["reference_branch"] == branch for row in selected)
        for branch in ("CONFIRMED_CANDIDATE", "LEGITIMATE_CANDIDATE")
    }
    report = {
        "report_id": "WAYBACK_LANGUAGE_EXPANSION_TOPUP_BALANCED_CAPTURE_PLAN_V2",
        "created_at": "2026-10-01",
        "status": "FROZEN_BALANCED_CAPTURE_PLAN_UNLABELED",
        "inputs": {
            "confirmed_availability": {"path": str(args.confirmed_availability), "sha256": args.confirmed_availability_sha256},
            "legitimate_availability": {"path": str(args.legitimate_availability), "sha256": args.legitimate_availability_sha256},
            "prior_capture_plans": [
                {"path": str(path), "sha256": expected}
                for path, expected in prior_plan_inputs
            ],
        },
        "selection_seed": args.seed,
        "excluded_prior_capture_candidate_count": len(excluded),
        "requested_candidate_count": len(selected),
        "requested_by_reference_branch": counts,
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
    print(json.dumps({"status": "OK", "output": str(args.output), "sha256": sha256_file(args.output), "selected_by_reference_branch": counts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
