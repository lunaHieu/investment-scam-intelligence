"""Build an exact SEC/IAPD capture plan from a complete V3, V4, or V5 result."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.capture_balanced_wayback_plan_v2 import raw_replay_url
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


REPORT_ID = "ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_CAPTURE_PLAN_V1"
PLAN_STATUS = "FROZEN_ALL_AND_ONLY_AVAILABLE_V3_SNAPSHOTS_UNLABELED"
REQUIRED_QA_STATUS = "PASS_COMPLETE_CAPTURE_PLAN_MAY_BE_PREPARED"
EXPECTED_COHORTS = {"DEVELOPMENT", "EXTERNAL_HOLDOUT"}
SUPPORTED_RESULTS = {
    "ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_AVAILABILITY_REPORT_V3": (
        "v3", "v3_sha256", "ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_RETRY_RELEASE_V3",
    ),
    "ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_AVAILABILITY_REPORT_V4": (
        "v4", "v4_sha256", "ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_RETRY_RELEASE_V4",
    ),
    "ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_AVAILABILITY_REPORT_V5": (
        "v5", "v5_sha256", "ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_RETRY_RELEASE_V5",
    ),
}


def result_contract(report_id: object) -> tuple[str, str, str]:
    try:
        return SUPPORTED_RESULTS[str(report_id)]
    except KeyError as error:
        raise ValueError("Unexpected availability report identity") from error


def safe_component(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]", "_", value)
    if not sanitized or sanitized in {".", ".."}:
        raise ValueError(f"Unsafe path component: {value}")
    return sanitized


def build_plan(
    *, release_path: Path, availability_path: Path, qa_path: Path,
    raw_root: Path, capture_date: str,
) -> dict[str, Any]:
    release = load_object(release_path)
    availability = load_object(availability_path)
    qa = load_object(qa_path)
    errors: list[str] = []
    generation = "unknown"
    qa_hash_key = ""
    expected_release_id = ""
    try:
        generation, qa_hash_key, expected_release_id = result_contract(availability.get("report_id"))
    except ValueError as error:
        errors.append(str(error))
    availability_sha256 = sha256_file(availability_path)
    release_sha256 = sha256_file(release_path)
    if availability.get("release_sha256") != release_sha256:
        errors.append("Availability result is not bound to the supplied release")
    if release.get("release_id") != expected_release_id or release.get("planned_output", {}).get("report_id") != availability.get("report_id"):
        errors.append("Availability result generation does not match the supplied release identity")
    if availability.get("status") != "COMPLETE" or availability.get("unresolved_error_count") != 0:
        errors.append("Availability result is not complete")
    if availability.get("capture_plan_construction_ready") is not True:
        errors.append("Availability result did not release capture-plan construction")
    if qa.get("status") != REQUIRED_QA_STATUS:
        errors.append("Independent availability QA did not pass the complete-result gate")
    if qa_hash_key and qa.get("inputs", {}).get(qa_hash_key) != availability_sha256:
        errors.append("Independent availability QA is not bound to the supplied result generation")
    if qa.get("checks", {}).get("capture_plan_construction_ready") is not True:
        errors.append("Independent availability QA kept capture-plan construction closed")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", capture_date):
        errors.append("capture-date must be YYYY-MM-DD")

    resolved_root = raw_root.resolve()
    capture_root = (
        resolved_root / "target_text_corpus_v1" /
        "sec_edgar_iapd_all_filer_wayback_snapshots_v1"
    ).resolve()
    if resolved_root not in capture_root.parents:
        errors.append("Capture root escaped raw data root")

    source_rows = list(availability.get("results", []))
    if len(source_rows) != 115:
        errors.append("Availability population is not exactly 115 rows")
    rows: list[dict[str, Any]] = []
    for source in source_rows:
        if source.get("available") is not True:
            continue
        try:
            replay_url, timestamp = raw_replay_url(str(source["snapshot_url"]))
            plan_id = safe_component(str(source["availability_plan_id"]))
            cohort = safe_component(str(source["cohort"]))
            host = safe_component(str(source["candidate_host"]).casefold().rstrip("."))
        except (KeyError, ValueError) as error:
            errors.append(f"Invalid available row: {error}")
            continue
        if source.get("cohort") not in EXPECTED_COHORTS:
            errors.append(f"Unexpected cohort: {source.get('cohort')}")
        target = (capture_root / cohort / f"{plan_id}__{host}.html").resolve()
        if capture_root not in target.parents:
            errors.append(f"Capture target escaped root: {target}")
        rows.append({
            "availability_plan_id": source["availability_plan_id"],
            "shortlist_id": source["shortlist_id"],
            "cohort": source["cohort"],
            "candidate_host": source["candidate_host"],
            "candidate_url": source["candidate_url"],
            "snapshot_timestamp": timestamp,
            "snapshot_url": source["snapshot_url"],
            "requested_archive_url": replay_url,
            "capture_path": str(target),
        })

    expected_ids = [
        str(row["availability_plan_id"])
        for row in source_rows if row.get("available") is True
    ]
    planned_ids = [str(row["availability_plan_id"]) for row in rows]
    if planned_ids != expected_ids:
        errors.append("Capture-plan order or membership differs from available rows")
    if not rows:
        errors.append("Availability result contains no capturable snapshot")
    if len(planned_ids) != len(set(planned_ids)):
        errors.append("Capture plan contains duplicate availability-plan IDs")
    targets = [str(row["capture_path"]) for row in rows]
    if len(targets) != len(set(targets)):
        errors.append("Capture plan contains duplicate target paths")
    if any(Path(target).exists() for target in targets):
        errors.append("One or more immutable capture targets already exist")
    if errors:
        raise ValueError(f"Capture plan validation failed: {errors}")

    counts = Counter(str(row["cohort"]) for row in rows)
    availability_binding = {
        "generation": generation,
        "path": str(availability_path.resolve()),
        "sha256": availability_sha256,
        "report_id": availability["report_id"],
        "created_at": availability.get("created_at"),
    }
    qa_binding = {
        "generation": generation,
        "path": str(qa_path.resolve()),
        "sha256": sha256_file(qa_path),
        "required_status": REQUIRED_QA_STATUS,
        "result_hash_field": qa_hash_key,
    }
    return {
        "report_id": REPORT_ID,
        "created_at": capture_date,
        # Retained so the already-frozen capture-release V1 contract remains compatible.
        "status": PLAN_STATUS,
        "availability_generation": generation,
        "release": {"path": str(release_path.resolve()), "sha256": release_sha256},
        "availability_result": availability_binding,
        "independent_availability_qa": qa_binding,
        "raw_root": str(resolved_root),
        "capture_root": str(capture_root),
        "capture_date": capture_date,
        "source_candidate_count": len(source_rows),
        "planned_capture_count": len(rows),
        "planned_by_cohort": dict(counts),
        "unavailable_candidates_not_planned": sum(row.get("available") is False for row in source_rows),
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
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--availability", type=Path, required=True)
    parser.add_argument("--availability-qa", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--capture-date", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite frozen capture plan")
    plan = build_plan(
        release_path=args.release,
        availability_path=args.availability,
        qa_path=args.availability_qa,
        raw_root=args.raw_root,
        capture_date=args.capture_date,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({
        "status": plan["status"],
        "availability_generation": plan["availability_generation"],
        "output": str(args.output),
        "sha256": sha256_file(args.output),
        "planned_capture_count": plan["planned_capture_count"],
        "planned_by_cohort": plan["planned_by_cohort"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
