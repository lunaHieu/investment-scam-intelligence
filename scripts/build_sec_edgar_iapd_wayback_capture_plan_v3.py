"""Build an exact SEC/IAPD capture plan from complete V3-V6 evidence."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.capture_balanced_wayback_plan_v2 import raw_replay_url
from scripts.verify_sec_edgar_iapd_wayback_availability_result_v1 import read_jsonl
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


REPORT_ID = "ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_CAPTURE_PLAN_V1"
# Kept for compatibility with the frozen capture executor and result verifier.
PLAN_STATUS = "FROZEN_ALL_AND_ONLY_AVAILABLE_V3_SNAPSHOTS_UNLABELED"
PLAN_QA_ID = "ISI_SEC_EDGAR_IAPD_WAYBACK_CAPTURE_PLAN_INDEPENDENT_QA_V3"
PLAN_QA_STATUS = "PASS_EXACT_AVAILABLE_SNAPSHOT_PLAN_REGISTER_BEFORE_EXECUTION"
REQUIRED_AVAILABILITY_QA_STATUS = "PASS_COMPLETE_CAPTURE_PLAN_MAY_BE_PREPARED"
EXPECTED_COHORTS = {"DEVELOPMENT", "EXTERNAL_HOLDOUT"}
IDENTITY_FIELDS = (
    "availability_plan_id", "shortlist_id", "cohort", "candidate_host", "candidate_url",
)
SUPPORTED_RESULTS = {
    f"ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_AVAILABILITY_REPORT_V{number}": {
        "generation": f"v{number}",
        "qa_hash_key": f"v{number}_sha256",
        "release_id": f"ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_RETRY_RELEASE_V{number}",
        "qa_id": f"ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_RESULT_INDEPENDENT_QA_V{number}",
    }
    for number in range(3, 7)
}


def result_contract(report_id: object) -> dict[str, str]:
    try:
        return SUPPORTED_RESULTS[str(report_id)]
    except KeyError as error:
        raise ValueError("Unexpected availability report identity") from error


def safe_component(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]", "_", value)
    if not sanitized or sanitized in {".", ".."}:
        raise ValueError(f"Unsafe path component: {value}")
    return sanitized


def validate_availability_population(
    release: dict[str, Any], availability: dict[str, Any], errors: list[str],
) -> list[dict[str, Any]]:
    plan_item = release.get("inputs", {}).get("availability_plan", {})
    plan_path = Path(str(plan_item.get("path", "")))
    try:
        if sha256_file(plan_path) != plan_item.get("sha256"):
            errors.append("Availability source-plan hash mismatch")
        source_plan = read_jsonl(plan_path)
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(f"Cannot read availability source plan: {error}")
        source_plan = []
    result_rows = list(availability.get("results", []))
    if len(source_plan) != 115 or plan_item.get("record_count") != 115:
        errors.append("Availability source population is not exactly 115 rows")
    if len(result_rows) != 115:
        errors.append("Availability result population is not exactly 115 rows")
    if len({row.get("availability_plan_id") for row in result_rows}) != len(result_rows):
        errors.append("Availability result contains duplicate plan IDs")
    available = unavailable = unresolved = 0
    for index, expected in enumerate(source_plan):
        if index >= len(result_rows):
            break
        observed = result_rows[index]
        for field in IDENTITY_FIELDS:
            if observed.get(field) != expected.get(field):
                errors.append(f"Availability source/result mismatch at row {index}: {field}")
        if observed.get("query_timestamp") != expected.get("target_timestamp"):
            errors.append(f"Availability source/result mismatch at row {index}: query_timestamp")
        if observed.get("error") is not None:
            unresolved += 1
            if observed.get("available") is not None:
                errors.append(f"Unresolved availability row has an availability value at row {index}")
        elif observed.get("available") is True:
            available += 1
            if not observed.get("snapshot_url") or not observed.get("snapshot_timestamp"):
                errors.append(f"Available row lacks snapshot evidence at row {index}")
        elif observed.get("available") is False:
            unavailable += 1
            if any(observed.get(field) is not None for field in (
                "snapshot_url", "snapshot_timestamp", "snapshot_http_status",
            )):
                errors.append(f"Unavailable row retains snapshot evidence at row {index}")
        else:
            errors.append(f"Resolved availability row lacks a boolean outcome at row {index}")
    if unresolved:
        errors.append("Availability result contains unresolved rows")
    for field, expected in (
        ("requested_candidate_count", len(source_plan)),
        ("available_snapshot_count", available),
        ("unavailable_snapshot_count", unavailable),
        ("unresolved_error_count", unresolved),
    ):
        if availability.get(field) != expected:
            errors.append(f"Availability aggregate mismatch: {field}")
    return result_rows


def build_plan(
    *, release_path: Path, availability_path: Path, qa_path: Path,
    raw_root: Path, capture_date: str,
) -> dict[str, Any]:
    release = load_object(release_path)
    availability = load_object(availability_path)
    qa = load_object(qa_path)
    errors: list[str] = []
    try:
        contract = result_contract(availability.get("report_id"))
    except ValueError as error:
        errors.append(str(error))
        contract = {"generation": "unknown", "qa_hash_key": "", "release_id": "", "qa_id": ""}
    generation = contract["generation"]
    availability_sha256 = sha256_file(availability_path)
    release_sha256 = sha256_file(release_path)
    if availability.get("release_sha256") != release_sha256:
        errors.append("Availability result is not bound to the supplied release")
    if (
        release.get("release_id") != contract["release_id"]
        or release.get("planned_output", {}).get("report_id") != availability.get("report_id")
    ):
        errors.append("Availability result generation does not match the supplied release identity")
    if availability.get("status") != "COMPLETE" or availability.get("unresolved_error_count") != 0:
        errors.append("Availability result is not complete")
    if availability.get("capture_plan_construction_ready") is not True:
        errors.append("Availability result did not release capture-plan construction")
    if qa.get("verification_id") != contract["qa_id"]:
        errors.append("Independent availability QA identity does not match result generation")
    if qa.get("status") != REQUIRED_AVAILABILITY_QA_STATUS:
        errors.append("Independent availability QA did not pass the complete-result gate")
    if qa.get("inputs", {}).get(contract["qa_hash_key"]) != availability_sha256:
        errors.append("Independent availability QA is not bound to the supplied result generation")
    foreign_hash_keys = {
        item["qa_hash_key"] for item in SUPPORTED_RESULTS.values()
        if item["qa_hash_key"] != contract["qa_hash_key"]
    }
    if any(key in qa.get("inputs", {}) for key in foreign_hash_keys):
        errors.append("Independent availability QA contains a cross-generation result binding")
    if qa.get("checks", {}).get("capture_plan_construction_ready") is not True:
        errors.append("Independent availability QA kept capture-plan construction closed")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", capture_date):
        errors.append("capture-date must be YYYY-MM-DD")

    source_rows = validate_availability_population(release, availability, errors)
    resolved_root = raw_root.resolve()
    capture_root = (
        resolved_root / "target_text_corpus_v1" /
        "sec_edgar_iapd_all_filer_wayback_snapshots_v1"
    ).resolve()
    if resolved_root not in capture_root.parents:
        errors.append("Capture root escaped raw data root")

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
            **{field: source[field] for field in IDENTITY_FIELDS},
            "snapshot_timestamp": timestamp,
            "snapshot_url": source["snapshot_url"],
            "requested_archive_url": replay_url,
            "capture_path": str(target),
        })

    expected_ids = [
        str(row["availability_plan_id"]) for row in source_rows if row.get("available") is True
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
    return {
        "report_id": REPORT_ID,
        "created_at": capture_date,
        "status": PLAN_STATUS,
        "tooling_version": "v3",
        "availability_generation": generation,
        "release": {"path": str(release_path.resolve()), "sha256": release_sha256},
        "availability_source_plan": {
            "path": str(Path(release["inputs"]["availability_plan"]["path"]).resolve()),
            "sha256": release["inputs"]["availability_plan"]["sha256"],
            "record_count": 115,
        },
        "availability_result": {
            "generation": generation,
            "path": str(availability_path.resolve()),
            "sha256": availability_sha256,
            "report_id": availability["report_id"],
            "created_at": availability.get("created_at"),
        },
        "independent_availability_qa": {
            "generation": generation,
            "path": str(qa_path.resolve()),
            "sha256": sha256_file(qa_path),
            "verification_id": contract["qa_id"],
            "required_status": REQUIRED_AVAILABILITY_QA_STATUS,
            "result_hash_field": contract["qa_hash_key"],
        },
        "raw_root": str(resolved_root),
        "capture_root": str(capture_root),
        "capture_date": capture_date,
        "source_candidate_count": len(source_rows),
        "planned_capture_count": len(rows),
        "planned_by_cohort": dict(counts),
        "unavailable_candidates_not_planned": sum(row.get("available") is False for row in source_rows),
        "results": rows,
        "safety_contract": {
            "network_operations": 0, "candidate_live_domain_access_operations": 0,
            "archived_page_download_operations": 0, "candidate_artifact_captures": 0,
            "labels_created": 0, "model_operations": 0, "training_allowed": False,
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
        release_path=args.release, availability_path=args.availability,
        qa_path=args.availability_qa, raw_root=args.raw_root,
        capture_date=args.capture_date,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({
        "status": plan["status"], "tooling_version": "v3",
        "availability_generation": plan["availability_generation"],
        "output": str(args.output), "sha256": sha256_file(args.output),
        "planned_capture_count": plan["planned_capture_count"],
        "planned_by_cohort": plan["planned_by_cohort"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
