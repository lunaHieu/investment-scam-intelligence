"""Paced, byte-preserving capture for the frozen Wayback holdout V3 plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.capture_balanced_wayback_plan_v2 import fetch_archive, raw_replay_url
from src.isi.normalization.external_references import sha256_file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--capture-date", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--delay-seconds", type=float, default=2.0)
    parser.add_argument("--retry-backoff-seconds", type=float, default=20.0)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--max-attempts", type=int, default=1)
    args = parser.parse_args()
    if args.report.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {args.report}")
    if sha256_file(args.plan) != args.plan_sha256:
        raise ValueError("Capture plan SHA-256 mismatch")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.capture_date):
        raise ValueError("capture-date must be YYYY-MM-DD")
    if args.delay_seconds < 0 or args.retry_backoff_seconds < 0 or args.max_attempts < 1:
        raise ValueError("Invalid capture pacing")
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    if plan.get("report_id") != "WAYBACK_HOLDOUT_BALANCED_CAPTURE_PLAN_V3":
        raise ValueError("Unexpected V3 capture plan")
    if int(plan.get("unresolved_error_count", -1)) != 0:
        raise ValueError("Capture plan contains unresolved availability errors")
    rows = list(plan["results"])
    branch_counts = {
        branch: sum(row.get("reference_branch") == branch for row in rows)
        for branch in ("CONFIRMED_CANDIDATE", "LEGITIMATE_CANDIDATE")
    }
    if len(set(branch_counts.values())) != 1 or min(branch_counts.values()) < 1:
        raise ValueError(f"Capture plan is not balanced: {branch_counts}")
    if any(row.get("available") is not True or row.get("error") for row in rows):
        raise ValueError("Capture plan includes an unavailable or unresolved row")
    target_dir = (
        args.raw_root
        / "external_text_captures"
        / args.capture_date
        / "matched_wayback_holdout_v3_balanced"
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    resolved_root = args.raw_root.resolve()
    resolved_target = target_dir.resolve()
    if resolved_root not in resolved_target.parents:
        raise ValueError(f"Capture target escaped raw root: {resolved_target}")
    results = []
    request_counter = [0]
    for row in rows:
        candidate_id = str(row["candidate_id"])
        candidate_host = str(row["candidate_host"]).casefold().rstrip(".")
        requested_url, timestamp = raw_replay_url(str(row["snapshot_url"]))
        safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", candidate_id)
        target_path = target_dir / f"{safe_id}__{candidate_host}.html"
        if target_path.exists():
            raise FileExistsError(f"Refusing to reuse existing capture target: {target_path}")
        final_error = None
        for attempt in range(1, args.max_attempts + 1):
            if attempt > 1:
                time.sleep(args.retry_backoff_seconds)
            try:
                payload, final_url, redirects, content_type = fetch_archive(
                    requested_url,
                    timeout_seconds=args.timeout_seconds,
                    delay_seconds=args.delay_seconds,
                    request_counter=request_counter,
                )
                with target_path.open("xb") as handle:
                    handle.write(payload)
                results.append({
                    "candidate_id": candidate_id,
                    "candidate_host": candidate_host,
                    "source_case_id": row["source_case_id"],
                    "reference_branch": row["reference_branch"],
                    "snapshot_timestamp": timestamp,
                    "requested_archive_url": requested_url,
                    "final_archive_url": final_url,
                    "redirect_count": redirects,
                    "http_status": 200,
                    "content_type": content_type,
                    "attempt_count": attempt,
                    "outcome": "CAPTURED",
                    "error": None,
                    "path": str(target_path),
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                })
                final_error = None
                break
            except Exception as error:
                final_error = f"{type(error).__name__}: {error}"
        if final_error:
            results.append({
                "candidate_id": candidate_id,
                "candidate_host": candidate_host,
                "source_case_id": row["source_case_id"],
                "reference_branch": row["reference_branch"],
                "snapshot_timestamp": timestamp,
                "requested_archive_url": requested_url,
                "final_archive_url": None,
                "redirect_count": None,
                "http_status": None,
                "content_type": None,
                "attempt_count": args.max_attempts,
                "outcome": "FAILED",
                "error": final_error,
                "path": None,
                "bytes": None,
                "sha256": None,
            })
    captured_by_branch = {
        branch: sum(
            row["reference_branch"] == branch and row["outcome"] == "CAPTURED"
            for row in results
        )
        for branch in branch_counts
    }
    report = {
        "report_id": "WAYBACK_HOLDOUT_BALANCED_CAPTURE_V3",
        "created_at": args.capture_date,
        "plan": str(args.plan),
        "plan_sha256": args.plan_sha256,
        "raw_root": str(resolved_root),
        "capture_directory": str(resolved_target),
        "requested_snapshot_count": len(rows),
        "requested_by_reference_branch": branch_counts,
        "network_request_count": request_counter[0],
        "captured_count": sum(row["outcome"] == "CAPTURED" for row in results),
        "captured_by_reference_branch": captured_by_branch,
        "failed_count": sum(row["outcome"] == "FAILED" for row in results),
        "results": results,
        "safety_contract": {
            "candidate_live_domain_access_operations": 0,
            "only_web_archive_host_accessed": True,
            "raw_replay_modifier_used": True,
            "automatic_external_redirect_following": False,
            "labels_created": 0,
            "model_scoring_operations": 0,
            "training_allowed": False,
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: report[key] for key in (
        "report_id", "requested_snapshot_count", "network_request_count",
        "captured_count", "captured_by_reference_branch", "failed_count"
    )}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
