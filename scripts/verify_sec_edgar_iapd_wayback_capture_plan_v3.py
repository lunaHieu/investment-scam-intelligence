"""Independently verify a V3-V6-derived SEC/IAPD capture plan."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.build_sec_edgar_iapd_wayback_capture_plan_v3 import (
    EXPECTED_COHORTS,
    IDENTITY_FIELDS,
    PLAN_QA_ID,
    PLAN_QA_STATUS,
    PLAN_STATUS,
    REPORT_ID,
    REQUIRED_AVAILABILITY_QA_STATUS,
    result_contract,
    validate_availability_population,
)
from scripts.capture_balanced_wayback_plan_v2 import assert_archive_url, raw_replay_url
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def verify(plan_path: Path, plan_sha256: str) -> dict[str, Any]:
    errors: list[str] = []
    try:
        observed_plan_hash = sha256_file(plan_path)
    except (FileNotFoundError, OSError) as error:
        return {"verification_id": PLAN_QA_ID, "status": "FAIL", "errors": [str(error)]}
    if observed_plan_hash != plan_sha256:
        errors.append("Capture plan SHA-256 mismatch")
    try:
        plan = load_object(plan_path)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as error:
        return {"verification_id": PLAN_QA_ID, "status": "FAIL", "errors": [str(error)]}
    if plan.get("report_id") != REPORT_ID or plan.get("status") != PLAN_STATUS:
        errors.append("Unexpected capture plan identity or status")
    if plan.get("tooling_version") != "v3":
        errors.append("Unexpected capture-plan tooling version")

    release_item = plan.get("release", {})
    availability_item = plan.get("availability_result", {})
    qa_item = plan.get("independent_availability_qa", {})
    source_plan_item = plan.get("availability_source_plan", {})
    release_path = Path(str(release_item.get("path", "")))
    availability_path = Path(str(availability_item.get("path", "")))
    qa_path = Path(str(qa_item.get("path", "")))
    source_plan_path = Path(str(source_plan_item.get("path", "")))
    for label, path, expected in (
        ("release", release_path, release_item.get("sha256")),
        ("availability", availability_path, availability_item.get("sha256")),
        ("independent QA", qa_path, qa_item.get("sha256")),
        ("availability source plan", source_plan_path, source_plan_item.get("sha256")),
    ):
        try:
            if sha256_file(path) != expected:
                errors.append(f"Capture plan {label} hash mismatch")
        except (FileNotFoundError, OSError):
            errors.append(f"Capture plan {label} input is missing")

    release: dict[str, Any] = {}
    availability: dict[str, Any] = {}
    qa: dict[str, Any] = {}
    contract = {"generation": "unknown", "qa_hash_key": "", "release_id": "", "qa_id": ""}
    try:
        release = load_object(release_path)
        availability = load_object(availability_path)
        qa = load_object(qa_path)
        contract = result_contract(availability.get("report_id"))
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as error:
        errors.append(f"Cannot read capture-plan evidence: {error}")
    generation = contract["generation"]
    if release.get("release_id") != contract["release_id"]:
        errors.append("Availability result/release generation mismatch")
    if release.get("planned_output", {}).get("report_id") != availability.get("report_id"):
        errors.append("Availability release planned-output identity mismatch")
    if availability.get("release_sha256") != release_item.get("sha256"):
        errors.append("Availability result/release hash binding mismatch")
    if availability.get("status") != "COMPLETE" or availability.get("unresolved_error_count") != 0:
        errors.append("Availability result is not complete")
    if availability.get("capture_plan_construction_ready") is not True:
        errors.append("Availability result kept capture-plan construction closed")
    if generation != plan.get("availability_generation"):
        errors.append("Availability generation binding mismatch")
    if any(item.get("generation") != generation for item in (availability_item, qa_item)):
        errors.append("Evidence generation binding mismatch")
    if availability_item.get("report_id") != availability.get("report_id"):
        errors.append("Availability report identity binding mismatch")
    if availability_item.get("created_at") != availability.get("created_at"):
        errors.append("Availability report timestamp binding mismatch")
    if qa.get("verification_id") != contract["qa_id"] or qa_item.get("verification_id") != contract["qa_id"]:
        errors.append("Independent availability QA identity/generation mismatch")
    if qa.get("status") != REQUIRED_AVAILABILITY_QA_STATUS:
        errors.append("Independent availability QA did not release capture-plan preparation")
    if qa_item.get("required_status") != REQUIRED_AVAILABILITY_QA_STATUS:
        errors.append("Capture plan QA status contract changed")
    if qa_item.get("result_hash_field") != contract["qa_hash_key"]:
        errors.append("Capture plan QA generation-specific hash field changed")
    if qa.get("inputs", {}).get(contract["qa_hash_key"]) != availability_item.get("sha256"):
        errors.append("Independent availability QA/result binding mismatch")
    foreign_hash_fields = {
        f"v{number}_sha256" for number in range(3, 7)
        if f"v{number}_sha256" != contract["qa_hash_key"]
    }
    if any(field in qa.get("inputs", {}) for field in foreign_hash_fields):
        errors.append("Independent availability QA contains a cross-generation result binding")
    if qa.get("checks", {}).get("capture_plan_construction_ready") is not True:
        errors.append("Independent availability QA kept capture-plan construction closed")
    if release.get("inputs", {}).get("availability_plan", {}) != source_plan_item:
        errors.append("Capture plan source-plan binding differs from availability release")

    source_rows = validate_availability_population(release, availability, errors)
    expected = [row for row in source_rows if row.get("available") is True]
    planned = list(plan.get("results", []))
    if plan.get("source_candidate_count") != 115:
        errors.append("Capture plan source count changed")
    if len(planned) != len(expected) or plan.get("planned_capture_count") != len(planned):
        errors.append("Capture plan count does not equal all available rows")
    keys = (*IDENTITY_FIELDS, "snapshot_timestamp", "snapshot_url")
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
        if capture_root not in Path(target).resolve().parents:
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
        "verification_id": PLAN_QA_ID,
        "status": PLAN_QA_STATUS if not errors else "FAIL",
        "plan": {"path": str(plan_path.resolve()), "sha256": observed_plan_hash},
        "checks": {
            "availability_generation": generation,
            "availability_hash_verified": not any("availability hash" in error.casefold() for error in errors),
            "availability_qa_hash_verified": not any("independent qa hash" in error.casefold() for error in errors),
            "source_plan_hash_verified": not any("source plan hash" in error.casefold() for error in errors),
            "complete_population_recomputed": not any(
                token in error for error in errors for token in ("unresolved", "aggregate mismatch", "population")
            ),
            "all_and_only_available_rows_planned_in_order": (
                len(planned) == len(expected)
                and not any("Availability/plan mismatch" in error for error in errors)
            ),
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
            "network_operations": 0, "candidate_domain_access_operations": 0,
            "archived_page_downloads": 0, "captures": 0, "labels": 0, "model": 0,
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
