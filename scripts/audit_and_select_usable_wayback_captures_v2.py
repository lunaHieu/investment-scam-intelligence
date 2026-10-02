"""Audit capture files without bypassing security controls and freeze a balanced usable view."""

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


def audit_capture(row: dict[str, object]) -> dict[str, object]:
    result = {
        "candidate_id": row["candidate_id"],
        "candidate_host": row["candidate_host"],
        "reference_branch": row["reference_branch"],
        "reported_outcome": row["outcome"],
        "path": row.get("path"),
        "reported_sha256": row.get("sha256"),
        "audit_state": None,
        "audit_error": None,
    }
    if row["outcome"] != "CAPTURED":
        result["audit_state"] = "ACQUISITION_FAILED"
        result["audit_error"] = row.get("error")
        return result
    path = Path(str(row["path"]))
    if not path.is_file():
        result["audit_state"] = "MISSING_AFTER_CAPTURE_POSSIBLE_SECURITY_QUARANTINE"
        result["audit_error"] = "Reported capture path is no longer a readable file; do not bypass endpoint protection."
        return result
    try:
        actual_hash = sha256_file(path)
    except OSError as error:
        result["audit_state"] = "UNREADABLE_SECURITY_OR_IO_BLOCK"
        result["audit_error"] = f"{type(error).__name__}: {error}"
        return result
    result["actual_sha256"] = actual_hash
    if actual_hash != row["sha256"]:
        result["audit_state"] = "HASH_MISMATCH"
        result["audit_error"] = "Current capture bytes do not match the acquisition report."
    else:
        result["audit_state"] = "HASH_VERIFIED_READABLE"
    return result


def select_balanced_usable(
    capture_rows: list[dict[str, object]],
    audit_rows: list[dict[str, object]],
    *,
    per_branch: int,
    seed: str,
) -> list[dict[str, object]]:
    states = {row["candidate_id"]: row["audit_state"] for row in audit_rows}
    pools = {
        branch: [
            row
            for row in capture_rows
            if row["reference_branch"] == branch
            and states.get(row["candidate_id"]) == "HASH_VERIFIED_READABLE"
        ]
        for branch in BRANCHES
    }
    for branch, pool in pools.items():
        if len(pool) < per_branch:
            raise ValueError(f"Insufficient usable {branch} captures: {len(pool)} < {per_branch}")
    selected = []
    for branch in BRANCHES:
        ranked = sorted(
            pools[branch],
            key=lambda row: hashlib.sha256(
                f"{seed}|{branch}|{row['candidate_id']}|{row['sha256']}".encode("utf-8")
            ).hexdigest(),
        )
        selected.extend(ranked[:per_branch])
    return sorted(selected, key=lambda row: str(row["candidate_id"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-report", type=Path, required=True)
    parser.add_argument("--capture-report-sha256", required=True)
    parser.add_argument("--per-branch", type=int, default=12)
    parser.add_argument("--seed", default="20261001-usable-capture-v2")
    parser.add_argument("--audit-output", type=Path, required=True)
    parser.add_argument("--balanced-output", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.audit_output, args.balanced_output):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite frozen output: {path}")
    if sha256_file(args.capture_report) != args.capture_report_sha256:
        raise ValueError("Capture report SHA-256 mismatch")
    source = json.loads(args.capture_report.read_text(encoding="utf-8"))
    audit_rows = [audit_capture(row) for row in source["results"]]
    state_counts: dict[str, int] = {}
    for row in audit_rows:
        state = str(row["audit_state"])
        state_counts[state] = state_counts.get(state, 0) + 1
    audit = {
        "analysis_id": "WAYBACK_LANGUAGE_EXPANSION_CAPTURE_ARTIFACT_AUDIT_V2",
        "created_at": "2026-10-01",
        "capture_report": str(args.capture_report),
        "capture_report_sha256": args.capture_report_sha256,
        "counts": state_counts,
        "records": audit_rows,
        "security_handling": {
            "endpoint_protection_bypassed": False,
            "blocked_or_missing_files_opened": False,
            "blocked_or_missing_files_eligible_for_processing": False,
            "interpretation": "A file missing after successful acquisition may have been quarantined, but the audit does not claim a malware verdict.",
        },
    }
    args.audit_output.parent.mkdir(parents=True, exist_ok=True)
    args.audit_output.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    selected = select_balanced_usable(
        source["results"], audit_rows, per_branch=args.per_branch, seed=args.seed
    )
    counts = {
        branch: sum(row["reference_branch"] == branch for row in selected)
        for branch in BRANCHES
    }
    balanced = {
        "report_id": "WAYBACK_LANGUAGE_EXPANSION_BALANCED_USABLE_CAPTURE_VIEW_V2",
        "created_at": "2026-10-01",
        "source_capture_report": str(args.capture_report),
        "source_capture_report_sha256": args.capture_report_sha256,
        "capture_audit": str(args.audit_output),
        "capture_audit_sha256": sha256_file(args.audit_output),
        "selection_seed": args.seed,
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
    print(
        json.dumps(
            {
                "status": "OK",
                "audit_output": str(args.audit_output),
                "audit_sha256": sha256_file(args.audit_output),
                "audit_counts": state_counts,
                "balanced_output": str(args.balanced_output),
                "balanced_sha256": sha256_file(args.balanced_output),
                "selected_by_reference_branch": counts,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
