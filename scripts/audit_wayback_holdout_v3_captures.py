"""Audit Wayback holdout V3 capture files and freeze the largest balanced usable view."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_and_select_usable_wayback_captures_v2 import BRANCHES, audit_capture
from src.isi.normalization.external_references import sha256_file


def select_largest_balanced(capture_rows, audit_rows, *, minimum_per_branch: int, seed: str):
    states = {row["candidate_id"]: row["audit_state"] for row in audit_rows}
    pools = {
        branch: [
            row for row in capture_rows
            if row["reference_branch"] == branch
            and states.get(row["candidate_id"]) == "HASH_VERIFIED_READABLE"
        ]
        for branch in BRANCHES
    }
    per_branch = min(len(pool) for pool in pools.values())
    if per_branch < minimum_per_branch:
        raise ValueError(
            f"Insufficient balanced usable captures: {per_branch} < {minimum_per_branch}"
        )
    selected = []
    for branch in BRANCHES:
        ranked = sorted(
            pools[branch],
            key=lambda row: hashlib.sha256(
                f"{seed}|{branch}|{row['candidate_id']}|{row['sha256']}".encode("utf-8")
            ).hexdigest(),
        )
        selected.extend(ranked[:per_branch])
    return sorted(selected, key=lambda row: str(row["candidate_id"])), per_branch


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-report", type=Path, required=True)
    parser.add_argument("--capture-report-sha256", required=True)
    parser.add_argument("--minimum-per-branch", type=int, default=12)
    parser.add_argument("--seed", default="20261002-wayback-holdout-v3-usable")
    parser.add_argument("--audit-output", type=Path, required=True)
    parser.add_argument("--balanced-output", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.audit_output, args.balanced_output):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite frozen output: {path}")
    if sha256_file(args.capture_report) != args.capture_report_sha256:
        raise ValueError("Capture report SHA-256 mismatch")
    source = json.loads(args.capture_report.read_text(encoding="utf-8"))
    if source.get("report_id") != "WAYBACK_HOLDOUT_BALANCED_CAPTURE_V3":
        raise ValueError("Unexpected capture report")
    audit_rows = [audit_capture(row) for row in source["results"]]
    state_counts = {}
    for row in audit_rows:
        state = str(row["audit_state"])
        state_counts[state] = state_counts.get(state, 0) + 1
    audit = {
        "analysis_id": "WAYBACK_HOLDOUT_CAPTURE_ARTIFACT_AUDIT_V3",
        "created_at": "2026-10-02",
        "capture_report": str(args.capture_report),
        "capture_report_sha256": args.capture_report_sha256,
        "counts": state_counts,
        "records": audit_rows,
        "security_handling": {
            "endpoint_protection_bypassed": False,
            "blocked_or_missing_files_opened": False,
            "blocked_or_missing_files_eligible_for_processing": False,
        },
    }
    args.audit_output.parent.mkdir(parents=True, exist_ok=True)
    args.audit_output.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    selected, per_branch = select_largest_balanced(
        source["results"], audit_rows,
        minimum_per_branch=args.minimum_per_branch, seed=args.seed,
    )
    counts = {
        branch: sum(row["reference_branch"] == branch for row in selected)
        for branch in BRANCHES
    }
    balanced = {
        "report_id": "WAYBACK_HOLDOUT_BALANCED_USABLE_CAPTURE_VIEW_V3",
        "created_at": "2026-10-02",
        "source_capture_report": str(args.capture_report),
        "source_capture_report_sha256": args.capture_report_sha256,
        "capture_audit": str(args.audit_output),
        "capture_audit_sha256": sha256_file(args.audit_output),
        "selection_seed": args.seed,
        "selected_per_branch": per_branch,
        "requested_snapshot_count": len(selected),
        "network_request_count": 0,
        "captured_count": len(selected),
        "captured_by_reference_branch": counts,
        "failed_count": 0,
        "results": selected,
        "safety_contract": {
            "network_operations": 0,
            "endpoint_protection_bypassed": False,
            "labels_created": 0,
            "model_scoring_operations": 0,
            "training_allowed": False,
        },
    }
    args.balanced_output.write_text(
        json.dumps(balanced, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "status": "OK",
        "audit_output": str(args.audit_output),
        "audit_sha256": sha256_file(args.audit_output),
        "audit_counts": state_counts,
        "balanced_output": str(args.balanced_output),
        "balanced_sha256": sha256_file(args.balanced_output),
        "selected_by_reference_branch": counts,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
