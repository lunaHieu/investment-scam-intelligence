"""Execute a verified, hash-bound SEC/IAPD Wayback capture release once."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.error
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.build_sec_edgar_iapd_wayback_capture_release_v1 import RELEASE_ID, parse_time
from scripts.capture_balanced_wayback_plan_v2 import fetch_archive
from scripts.verify_sec_edgar_iapd_wayback_capture_release_v1 import verify
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


RELEASE_QA_STATUS = "PASS_ARCHIVE_ONLY_CAPTURE_RELEASE"


def validate_release(release_path: Path, qa_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    release = load_object(release_path)
    qa = load_object(qa_path)
    errors: list[str] = []
    if release.get("release_id") != RELEASE_ID:
        errors.append("Unexpected capture release identity")
    if qa.get("status") != RELEASE_QA_STATUS:
        errors.append("Capture release independent QA did not pass")
    if qa.get("release", {}).get("sha256") != sha256_file(release_path):
        errors.append("Capture release QA hash mismatch")
    if qa.get("decision", {}).get("execution_allowed_at_or_after_not_before") is not True:
        errors.append("Capture release QA did not open execution after not-before")
    reproduced = verify(release_path)
    if reproduced.get("status") != RELEASE_QA_STATUS or reproduced.get("errors"):
        errors.append("Capture release no longer passes its frozen verifier")
    plan_path = Path(release["inputs"]["capture_plan"]["path"])
    if sha256_file(plan_path) != release["inputs"]["capture_plan"]["sha256"]:
        errors.append("Capture plan hash changed")
    plan = load_object(plan_path)
    report_path = Path(release["planned_output"]["path"])
    if report_path.exists() or report_path.with_suffix(report_path.suffix + ".partial").exists():
        errors.append("Capture report or partial report already exists")
    existing = [row["capture_path"] for row in plan["results"] if Path(row["capture_path"]).exists()]
    if existing:
        errors.append("One or more immutable raw capture targets already exist")
    if errors:
        raise ValueError(f"Capture execution validation failed: {errors}")
    return release, plan


def execute(
    release_path: Path, qa_path: Path, now: datetime | None = None,
) -> dict[str, Any]:
    release, plan = validate_release(release_path, qa_path)
    current = now or datetime.now(timezone.utc).astimezone()
    if current.tzinfo is None:
        raise ValueError("Current time must include a timezone")
    not_before = parse_time(release["execution_contract"]["not_before"])
    if current < not_before:
        raise PermissionError(f"Capture not-before gate is closed for {(not_before - current).total_seconds():.0f} seconds")
    contract = release["execution_contract"]
    request_counter = [0]
    results: list[dict[str, Any]] = []
    stopped = False
    for source in plan["results"]:
        base = {key: source[key] for key in (
            "availability_plan_id", "shortlist_id", "cohort", "candidate_host",
            "candidate_url", "snapshot_timestamp", "snapshot_url",
            "requested_archive_url", "capture_path",
        )}
        if stopped:
            results.append({
                **base, "outcome": "NOT_ATTEMPTED_AFTER_HTTP_429_STOP",
                "final_archive_url": None, "redirect_count": None,
                "http_status": None, "content_type": None, "bytes": None,
                "sha256": None, "error": "NOT_ATTEMPTED_AFTER_HTTP_429_STOP",
            })
            continue
        try:
            payload, final_url, redirects, content_type = fetch_archive(
                source["requested_archive_url"],
                timeout_seconds=int(contract["timeout_seconds"]),
                delay_seconds=float(contract["minimum_delay_seconds"]),
                request_counter=request_counter,
                max_redirects=int(contract["maximum_redirects"]),
            )
            target = Path(source["capture_path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                handle.write(payload)
            results.append({
                **base, "outcome": "CAPTURED", "final_archive_url": final_url,
                "redirect_count": redirects, "http_status": 200,
                "content_type": content_type, "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(), "error": None,
            })
        except urllib.error.HTTPError as error:
            if error.code == 429:
                stopped = True
            results.append({
                **base, "outcome": "FAILED", "final_archive_url": None,
                "redirect_count": None, "http_status": error.code,
                "content_type": None, "bytes": None, "sha256": None,
                "error": f"HTTPError: {error}",
            })
        except Exception as error:
            results.append({
                **base, "outcome": "FAILED", "final_archive_url": None,
                "redirect_count": None, "http_status": None,
                "content_type": None, "bytes": None, "sha256": None,
                "error": f"{type(error).__name__}: {error}",
            })
    captured = sum(row["outcome"] == "CAPTURED" for row in results)
    failed = sum(row["outcome"] == "FAILED" for row in results)
    not_attempted = sum(row["outcome"] == "NOT_ATTEMPTED_AFTER_HTTP_429_STOP" for row in results)
    report = {
        "report_id": release["planned_output"]["report_id"],
        "created_at": current.isoformat(),
        "status": "COMPLETE" if captured == len(results) else "INCOMPLETE_FAILURES_PRESERVED",
        "release": {"path": str(release_path.resolve()), "sha256": sha256_file(release_path)},
        "release_qa": {"path": str(qa_path.resolve()), "sha256": sha256_file(qa_path)},
        "plan": release["inputs"]["capture_plan"],
        "planned_capture_count": len(results),
        "network_request_count": request_counter[0],
        "captured_count": captured,
        "captured_by_cohort": dict(Counter(row["cohort"] for row in results if row["outcome"] == "CAPTURED")),
        "failed_count": failed,
        "not_attempted_count": not_attempted,
        "stopped_on_http_429": stopped,
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
    report_path = Path(release["planned_output"]["path"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    partial = report_path.with_suffix(report_path.suffix + ".partial")
    partial.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(report_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-qa", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        release, plan = validate_release(args.release, args.release_qa)
        remaining = max(0.0, (parse_time(release["execution_contract"]["not_before"]) - datetime.now(timezone.utc).astimezone()).total_seconds())
        print(json.dumps({"valid": True, "planned_capture_count": plan["planned_capture_count"], "seconds_until_not_before": round(remaining)}, indent=2))
        return 0
    report = execute(args.release, args.release_qa)
    print(json.dumps({key: report[key] for key in (
        "report_id", "status", "planned_capture_count", "network_request_count",
        "captured_count", "captured_by_cohort", "failed_count",
        "not_attempted_count", "stopped_on_http_429",
    )}, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
