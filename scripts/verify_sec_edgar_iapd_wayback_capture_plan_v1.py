"""Independently verify a SEC/IAPD Wayback capture plan before download."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.build_sec_edgar_iapd_wayback_capture_plan_v1 import (
    EXPECTED_COHORTS,
    EXPECTED_RESULT_ID,
    REPORT_ID,
    REQUIRED_QA_STATUS,
)
from scripts.capture_balanced_wayback_plan_v2 import assert_archive_url, raw_replay_url
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def verify(plan_path: Path, plan_sha256: str) -> dict[str, Any]:
    errors: list[str] = []
    if sha256_file(plan_path) != plan_sha256:
        errors.append("Capture plan SHA-256 mismatch")
    try:
        plan = load_object(plan_path)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as error:
        return {"verification_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_CAPTURE_PLAN_INDEPENDENT_QA_V1", "status": "FAIL", "errors": [str(error)]}
    if plan.get("report_id") != REPORT_ID:
        errors.append("Unexpected capture plan identity")
    if plan.get("status") != "FROZEN_ALL_AND_ONLY_AVAILABLE_V3_SNAPSHOTS_UNLABELED":
        errors.append("Unexpected capture plan status")

    availability_path = Path(str(plan.get("availability_v3", {}).get("path", "")))
    qa_path = Path(str(plan.get("independent_qa_v3", {}).get("path", "")))
    release_path = Path(str(plan.get("release", {}).get("path", "")))
    for label, path, expected in (
        ("availability", availability_path, plan.get("availability_v3", {}).get("sha256")),
        ("independent QA", qa_path, plan.get("independent_qa_v3", {}).get("sha256")),
        ("release", release_path, plan.get("release", {}).get("sha256")),
    ):
        try:
            if sha256_file(path) != expected:
                errors.append(f"Capture plan {label} hash mismatch")
        except (FileNotFoundError, OSError):
            errors.append(f"Capture plan {label} input is missing")

    availability: dict[str, Any] = {}
    qa: dict[str, Any] = {}
    try:
        availability = load_object(availability_path)
        qa = load_object(qa_path)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as error:
        errors.append(f"Cannot read capture-plan evidence: {error}")
    if availability.get("report_id") != EXPECTED_RESULT_ID or availability.get("status") != "COMPLETE":
        errors.append("Availability V3 is not the complete expected result")
    if availability.get("unresolved_error_count") != 0:
        errors.append("Availability V3 contains unresolved rows")
    if qa.get("status") != REQUIRED_QA_STATUS or qa.get("checks", {}).get("capture_plan_construction_ready") is not True:
        errors.append("Independent V3 QA did not release capture-plan preparation")
    if qa.get("inputs", {}).get("v3_sha256") != plan.get("availability_v3", {}).get("sha256"):
        errors.append("Independent V3 QA/result binding mismatch")

    source_rows = list(availability.get("results", []))
    expected = [row for row in source_rows if row.get("available") is True]
    planned = list(plan.get("results", []))
    if len(source_rows) != 115:
        errors.append("Availability V3 population is not exactly 115 rows")
    if plan.get("source_candidate_count") != 115:
        errors.append("Capture plan source count changed")
    if len(planned) != len(expected) or plan.get("planned_capture_count") != len(planned):
        errors.append("Capture plan count does not equal all available V3 rows")

    keys = (
        "availability_plan_id", "shortlist_id", "cohort", "candidate_host",
        "candidate_url", "snapshot_timestamp", "snapshot_url",
    )
    for index, source in enumerate(expected):
        if index >= len(planned):
            break
        row = planned[index]
        for key in keys:
            if row.get(key) != source.get(key):
                errors.append(f"Availability/plan mismatch at row {index}: {key}")
        try:
            replay_url, timestamp = raw_replay_url(str(row["snapshot_url"]))
            assert_archive_url(str(row["requested_archive_url"]))
            if row.get("requested_archive_url") != replay_url or row.get("snapshot_timestamp") != timestamp:
                errors.append(f"Raw replay mismatch at row {index}")
        except (KeyError, ValueError) as error:
            errors.append(f"Invalid archive URL at row {index}: {error}")

    planned_ids = [str(row.get("availability_plan_id")) for row in planned]
    targets = [str(row.get("capture_path")) for row in planned]
    if len(planned_ids) != len(set(planned_ids)) or len(targets) != len(set(targets)):
        errors.append("Capture plan contains duplicate IDs or targets")
    raw_root = Path(str(plan.get("raw_root", ""))).resolve()
    capture_root = Path(str(plan.get("capture_root", ""))).resolve()
    if raw_root not in capture_root.parents:
        errors.append("Capture root escaped raw root")
    for target in targets:
        resolved = Path(target).resolve()
        if capture_root not in resolved.parents:
            errors.append(f"Capture target escaped capture root: {target}")
    observed_counts = Counter(str(row.get("cohort")) for row in planned)
    if set(observed_counts) - EXPECTED_COHORTS:
        errors.append("Capture plan contains an unexpected cohort")
    if dict(observed_counts) != plan.get("planned_by_cohort"):
        errors.append("Capture plan cohort aggregate mismatch")
    unavailable = sum(row.get("available") is False for row in source_rows)
    if plan.get("unavailable_candidates_not_planned") != unavailable:
        errors.append("Unavailable aggregate mismatch")

    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_CAPTURE_PLAN_INDEPENDENT_QA_V1",
        "status": "PASS_EXACT_AVAILABLE_SNAPSHOT_PLAN_REGISTER_BEFORE_EXECUTION" if not errors else "FAIL",
        "plan": {"path": str(plan_path.resolve()), "sha256": sha256_file(plan_path)},
        "checks": {
            "availability_v3_hash_verified": not any("availability hash" in error for error in errors),
            "availability_qa_v3_hash_verified": not any("independent QA hash" in error for error in errors),
            "all_and_only_available_rows_planned_in_order": len(planned) == len(expected) and not any("Availability/plan mismatch" in error for error in errors),
            "planned_capture_count": len(planned),
            "planned_by_cohort": dict(observed_counts),
            "raw_replay_modifier_used": all("id_/" in str(row.get("requested_archive_url")) for row in planned),
        },
        "decision": {
            "capture_plan_qa_passed": not errors,
            "capture_execution_release_may_be_prepared": not errors,
            "archived_page_download_allowed_by_this_qa": False,
            "live_candidate_domain_access_allowed": False,
            "binary_labeling_allowed": False,
            "validation_or_test_opening_allowed": False,
            "training_allowed": False,
        },
        "errors": errors,
        "safety_contract": {
            "network_operations": 0,
            "candidate_domain_access_operations": 0,
            "archived_page_downloads": 0,
            "captures": 0,
            "labels": 0,
            "model": 0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite capture-plan QA")
    result = verify(args.plan, args.plan_sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
