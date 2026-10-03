"""Freeze an exact capture plan for all available Target Text Corpus V1 snapshots."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.capture_balanced_wayback_plan_v2 import raw_replay_url
from scripts.query_target_text_corpus_v1_wayback_availability import load_json, sha256_file


EXPECTED_AVAILABLE_BY_CHANNEL = {
    "CONFIRMED_REGULATOR_LINKED_WEBSITE": 5,
    "CONFIRMED_CFTC_RED_LINKED_WAYBACK_WEBSITE": 7,
    "LEGITIMATE_REGISTER_LINKED_WEBSITE": 8,
    "LEGITIMATE_SEC_EDGAR_LINKED_WAYBACK_WEBSITE": 9,
}


def safe_component(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]", "_", value)
    if not sanitized or sanitized in {".", ".."}:
        raise ValueError(f"Unsafe path component: {value}")
    return sanitized


def build_plan(
    *, availability_path: Path, qa_path: Path, raw_root: Path, capture_date: str
) -> dict[str, Any]:
    availability = load_json(availability_path)
    qa = load_json(qa_path)
    errors: list[str] = []
    if availability.get("report_id") != "ISI_TARGET_TEXT_CORPUS_V1_WAYBACK_AVAILABILITY_REPORT_V2":
        errors.append("Unexpected availability report ID")
    if availability.get("status") != "COMPLETE" or availability.get("unresolved_error_count") != 0:
        errors.append("Availability report is not complete")
    if qa.get("status") != "PASS_40_RESOLVED_29_AVAILABLE_CAPTURE_PLAN_BLOCKED":
        errors.append("Independent availability QA did not pass")
    if qa.get("inputs", {}).get("availability_v2", {}).get("sha256") != sha256_file(
        availability_path
    ):
        errors.append("Independent QA availability hash mismatch")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", capture_date):
        errors.append("capture-date must be YYYY-MM-DD")
    resolved_root = raw_root.resolve()
    capture_root = (resolved_root / "target_text_corpus_v1" / "wayback_snapshots_v1").resolve()
    if resolved_root not in capture_root.parents:
        errors.append("Capture root escaped raw data root")
    rows: list[dict[str, Any]] = []
    for source in availability.get("results", []):
        if source.get("available") is not True:
            continue
        try:
            replay_url, timestamp = raw_replay_url(str(source["snapshot_url"]))
            channel = safe_component(str(source["channel_id"]))
            candidate_id = safe_component(str(source["candidate_id"]))
            host = safe_component(str(source["candidate_host"]))
        except (KeyError, ValueError) as error:
            errors.append(f"Invalid available row: {error}")
            continue
        target = (capture_root / channel / f"{candidate_id}__{host}.html").resolve()
        if capture_root not in target.parents:
            errors.append(f"Capture target escaped root: {target}")
        rows.append({
            "candidate_id": source["candidate_id"],
            "channel_id": source["channel_id"],
            "channel_target_stratum": source["channel_target_stratum"],
            "candidate_host": source["candidate_host"],
            "candidate_url": source["candidate_url"],
            "snapshot_timestamp": timestamp,
            "snapshot_url": source["snapshot_url"],
            "requested_archive_url": replay_url,
            "capture_path": str(target),
        })
    rows.sort(key=lambda row: str(row["candidate_id"]))
    counts = Counter(str(row["channel_id"]) for row in rows)
    if len(rows) != 29 or dict(counts) != EXPECTED_AVAILABLE_BY_CHANNEL:
        errors.append(f"Available capture population changed: {len(rows)}, {dict(counts)}")
    ids = [str(row["candidate_id"]) for row in rows]
    hosts = [str(row["candidate_host"]) for row in rows]
    targets = [str(row["capture_path"]) for row in rows]
    if len(ids) != len(set(ids)) or len(hosts) != len(set(hosts)):
        errors.append("Capture plan contains duplicate candidate IDs or hosts")
    if len(targets) != len(set(targets)):
        errors.append("Capture plan contains duplicate target paths")
    existing_targets = [target for target in targets if Path(target).exists()]
    if existing_targets:
        errors.append("One or more immutable capture targets already exist")
    if errors:
        raise ValueError(f"Capture plan validation failed: {errors}")
    return {
        "report_id": "ISI_TARGET_TEXT_CORPUS_V1_WAYBACK_CAPTURE_PLAN_V1",
        "created_at": capture_date,
        "status": "FROZEN_EXACT_29_ARCHIVE_SNAPSHOTS_UNLABELED",
        "availability_report": str(availability_path.resolve()),
        "availability_report_sha256": sha256_file(availability_path),
        "independent_availability_qa": str(qa_path.resolve()),
        "independent_availability_qa_sha256": sha256_file(qa_path),
        "raw_root": str(resolved_root),
        "capture_root": str(capture_root),
        "capture_date": capture_date,
        "planned_capture_count": len(rows),
        "planned_by_channel": dict(counts),
        "unavailable_candidates_not_planned": 11,
        "results": rows,
        "safety_contract": {
            "network_operations": 0,
            "candidate_live_domain_access_operations": 0,
            "archived_page_download_operations": 0,
            "candidate_artifact_captures": 0,
            "labels_created": 0,
            "model_operations": 0,
            "training_allowed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--availability-report", type=Path, required=True)
    parser.add_argument("--availability-qa", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--capture-date", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {args.output}")
    plan = build_plan(
        availability_path=args.availability_report,
        qa_path=args.availability_qa,
        raw_root=args.raw_root,
        capture_date=args.capture_date,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(plan, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({
        "status": plan["status"],
        "output": str(args.output),
        "sha256": sha256_file(args.output),
        "planned_capture_count": plan["planned_capture_count"],
        "planned_by_channel": plan["planned_by_channel"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
