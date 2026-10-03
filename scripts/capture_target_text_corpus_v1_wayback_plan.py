"""Paced, fail-closed capture of a frozen Target Text Corpus V1 Wayback plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.capture_balanced_wayback_plan_v2 import (
    assert_archive_url,
    fetch_archive,
    raw_replay_url,
)
from scripts.query_target_text_corpus_v1_wayback_availability import load_json, sha256_file


EXPECTED_BY_CHANNEL = {
    "CONFIRMED_REGULATOR_LINKED_WEBSITE": 5,
    "CONFIRMED_CFTC_RED_LINKED_WAYBACK_WEBSITE": 7,
    "LEGITIMATE_REGISTER_LINKED_WEBSITE": 8,
    "LEGITIMATE_SEC_EDGAR_LINKED_WAYBACK_WEBSITE": 9,
}


def validate_plan(plan_path: Path, expected_sha256: str) -> dict[str, Any]:
    if sha256_file(plan_path) != expected_sha256:
        raise ValueError("Capture plan SHA-256 mismatch")
    plan = load_json(plan_path)
    if plan.get("report_id") != "ISI_TARGET_TEXT_CORPUS_V1_WAYBACK_CAPTURE_PLAN_V1":
        raise ValueError("Unexpected capture plan ID")
    if plan.get("status") != "FROZEN_EXACT_29_ARCHIVE_SNAPSHOTS_UNLABELED":
        raise ValueError("Unexpected capture plan status")
    rows = list(plan.get("results", []))
    counts = Counter(str(row.get("channel_id")) for row in rows)
    if len(rows) != 29 or dict(counts) != EXPECTED_BY_CHANNEL:
        raise ValueError(f"Capture plan population changed: {len(rows)}, {dict(counts)}")
    capture_root = Path(str(plan["capture_root"])).resolve()
    raw_root = Path(str(plan["raw_root"])).resolve()
    if raw_root not in capture_root.parents:
        raise ValueError("Capture root escaped raw root")
    for row in rows:
        target = Path(str(row["capture_path"])).resolve()
        if capture_root not in target.parents:
            raise ValueError(f"Capture target escaped capture root: {target}")
        expected_url, expected_timestamp = raw_replay_url(str(row["snapshot_url"]))
        if row.get("requested_archive_url") != expected_url:
            raise ValueError(f"Raw replay URL mismatch: {row.get('candidate_id')}")
        if row.get("snapshot_timestamp") != expected_timestamp:
            raise ValueError(f"Snapshot timestamp mismatch: {row.get('candidate_id')}")
        assert_archive_url(str(row["requested_archive_url"]))
    return plan


def execute(
    *, plan_path: Path, plan_sha256: str, report_path: Path,
    delay_seconds: float, timeout_seconds: int
) -> dict[str, Any]:
    if report_path.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {report_path}")
    if delay_seconds < 6.0:
        raise ValueError("Capture delay must be at least 6 seconds")
    plan = validate_plan(plan_path, plan_sha256)
    rows = list(plan["results"])
    for row in rows:
        if Path(str(row["capture_path"])).exists():
            raise FileExistsError(f"Refusing to reuse capture target: {row['capture_path']}")
    request_counter = [0]
    results: list[dict[str, Any]] = []
    stopped_on_429 = False
    for row in rows:
        base = {
            key: row[key]
            for key in (
                "candidate_id", "channel_id", "channel_target_stratum",
                "candidate_host", "candidate_url", "snapshot_timestamp",
                "snapshot_url", "requested_archive_url", "capture_path"
            )
        }
        if stopped_on_429:
            results.append({
                **base,
                "outcome": "NOT_ATTEMPTED_AFTER_HTTP_429_STOP",
                "final_archive_url": None,
                "redirect_count": None,
                "http_status": None,
                "content_type": None,
                "bytes": None,
                "sha256": None,
                "error": "NOT_ATTEMPTED_AFTER_HTTP_429_STOP",
            })
            continue
        try:
            payload, final_url, redirects, content_type = fetch_archive(
                str(row["requested_archive_url"]),
                timeout_seconds=timeout_seconds,
                delay_seconds=delay_seconds,
                request_counter=request_counter,
            )
            target = Path(str(row["capture_path"]))
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                handle.write(payload)
            results.append({
                **base,
                "outcome": "CAPTURED",
                "final_archive_url": final_url,
                "redirect_count": redirects,
                "http_status": 200,
                "content_type": content_type,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "error": None,
            })
        except urllib.error.HTTPError as error:
            if error.code == 429:
                stopped_on_429 = True
            results.append({
                **base,
                "outcome": "FAILED",
                "final_archive_url": None,
                "redirect_count": None,
                "http_status": error.code,
                "content_type": None,
                "bytes": None,
                "sha256": None,
                "error": f"HTTPError: {error}",
            })
        except Exception as error:  # preserve exact capture failure
            results.append({
                **base,
                "outcome": "FAILED",
                "final_archive_url": None,
                "redirect_count": None,
                "http_status": None,
                "content_type": None,
                "bytes": None,
                "sha256": None,
                "error": f"{type(error).__name__}: {error}",
            })
    captured_by_channel = Counter(
        str(row["channel_id"]) for row in results if row["outcome"] == "CAPTURED"
    )
    report = {
        "report_id": "ISI_TARGET_TEXT_CORPUS_V1_WAYBACK_CAPTURE_REPORT_V1",
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "status": "COMPLETE" if all(row["outcome"] == "CAPTURED" for row in results) else "INCOMPLETE_FAILURES_PRESERVED",
        "plan_path": str(plan_path.resolve()),
        "plan_sha256": plan_sha256,
        "planned_capture_count": len(rows),
        "network_request_count": request_counter[0],
        "captured_count": sum(row["outcome"] == "CAPTURED" for row in results),
        "captured_by_channel": dict(captured_by_channel),
        "failed_count": sum(row["outcome"] == "FAILED" for row in results),
        "not_attempted_count": sum(
            row["outcome"] == "NOT_ATTEMPTED_AFTER_HTTP_429_STOP" for row in results
        ),
        "stopped_on_http_429": stopped_on_429,
        "results": results,
        "safety_contract": {
            "candidate_live_domain_access_operations": 0,
            "only_web_archive_host_accessed": True,
            "raw_replay_modifier_used": True,
            "automatic_external_redirect_following": False,
            "labels_created": 0,
            "model_operations": 0,
            "training_allowed": False,
        },
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--delay-seconds", type=float, default=6.0)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    args = parser.parse_args()
    report = execute(
        plan_path=args.plan,
        plan_sha256=args.plan_sha256,
        report_path=args.report,
        delay_seconds=args.delay_seconds,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps({key: report[key] for key in (
        "report_id", "status", "planned_capture_count", "network_request_count",
        "captured_count", "captured_by_channel", "failed_count",
        "not_attempted_count", "stopped_on_http_429"
    )}, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
