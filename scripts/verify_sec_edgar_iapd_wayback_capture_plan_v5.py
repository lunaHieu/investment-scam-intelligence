"""Independently verify the amended V8 partial-resolved capture plan V5."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.build_sec_edgar_iapd_wayback_capture_plan_v5 import (
    AVAILABILITY_QA_ID,
    AVAILABILITY_RELEASE_ID,
    AVAILABILITY_REPORT_ID,
    EXPECTED_COHORTS,
    IDENTITY_FIELDS,
    PLAN_QA_ID,
    PLAN_QA_STATUS,
    PLAN_STATUS,
    REPORT_ID,
    REQUIRED_AVAILABILITY_QA_STATUS,
    validate_population,
)
from scripts.capture_balanced_wayback_plan_v2 import assert_archive_url, raw_replay_url
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def verify(plan_path: Path, plan_sha256: str) -> dict[str, Any]:
    errors: list[str] = []
    try:
        observed_hash = sha256_file(plan_path)
    except (FileNotFoundError, OSError) as error:
        return {"verification_id": PLAN_QA_ID, "status": "FAIL", "errors": [str(error)]}
    if observed_hash != plan_sha256:
        errors.append("Capture plan SHA-256 mismatch")
    try:
        plan = load_object(plan_path)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        return {"verification_id": PLAN_QA_ID, "status": "FAIL", "errors": [str(error)]}
    if (
        plan.get("report_id") != REPORT_ID
        or plan.get("status") != PLAN_STATUS
        or plan.get("tooling_version") != "v5"
        or plan.get("availability_generation") != "v8"
    ):
        errors.append("Unexpected capture-plan V5 identity, status, or generation")

    release_item = plan.get("release", {})
    result_item = plan.get("availability_result", {})
    qa_item = plan.get("independent_availability_qa", {})
    source_item = plan.get("availability_source_plan", {})
    release_path = Path(str(release_item.get("path", "")))
    result_path = Path(str(result_item.get("path", "")))
    qa_path = Path(str(qa_item.get("path", "")))
    source_path = Path(str(source_item.get("path", "")))
    for label, path, expected in (
        ("release", release_path, release_item.get("sha256")),
        ("availability result", result_path, result_item.get("sha256")),
        ("independent QA", qa_path, qa_item.get("sha256")),
        ("availability source plan", source_path, source_item.get("sha256")),
    ):
        try:
            if sha256_file(path) != expected:
                errors.append(f"Capture plan {label} hash mismatch")
        except (FileNotFoundError, OSError):
            errors.append(f"Capture plan {label} is missing")

    try:
        release = load_object(release_path)
        availability = load_object(result_path)
        qa = load_object(qa_path)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        release, availability, qa = {}, {}, {}
        errors.append(f"Cannot read V5 capture-plan evidence: {error}")
    if release.get("release_id") != AVAILABILITY_RELEASE_ID:
        errors.append("Unexpected V8 availability release identity")
    if availability.get("report_id") != AVAILABILITY_REPORT_ID:
        errors.append("Unexpected V8 availability report identity")
    if release.get("planned_output", {}).get("report_id") != AVAILABILITY_REPORT_ID:
        errors.append("V8 release planned-output identity mismatch")
    if availability.get("release_sha256") != release_item.get("sha256"):
        errors.append("V8 result/release hash binding mismatch")
    if availability.get("status") != "INCOMPLETE_ERRORS_PRESERVED" or availability.get("unresolved_error_count") != 2:
        errors.append("V8 availability result is not the exact verified two-row partial")
    if availability.get("capture_plan_construction_ready") is not False:
        errors.append("V8 partial readiness flag changed")
    if result_item.get("generation") != "v8" or qa_item.get("generation") != "v8":
        errors.append("Capture-plan evidence generation changed")
    if result_item.get("report_id") != availability.get("report_id"):
        errors.append("Availability report identity binding mismatch")
    if result_item.get("created_at") != availability.get("created_at"):
        errors.append("Availability report timestamp binding mismatch")
    if qa.get("verification_id") != AVAILABILITY_QA_ID or qa_item.get("verification_id") != AVAILABILITY_QA_ID:
        errors.append("Unexpected V8 independent QA identity")
    if qa.get("status") != REQUIRED_AVAILABILITY_QA_STATUS:
        errors.append("V8 independent QA did not pass the preserved-partial gate")
    if qa_item.get("required_status") != REQUIRED_AVAILABILITY_QA_STATUS:
        errors.append("Capture-plan QA status contract changed")
    if qa_item.get("result_hash_field") != "v8_sha256":
        errors.append("Capture-plan QA hash-field contract changed")
    if qa.get("inputs", {}).get("v8_sha256") != result_item.get("sha256"):
        errors.append("V8 independent QA/result binding mismatch")
    if any(f"v{number}_sha256" in qa.get("inputs", {}) for number in range(3, 7)):
        errors.append("V8 independent QA contains a prior-generation result binding")
    if qa.get("checks", {}).get("capture_plan_construction_ready") is not False:
        errors.append("V8 independent QA readiness flag changed")
    if qa.get("checks", {}).get("unresolved_results") != 2:
        errors.append("V8 independent QA unresolved count changed")
    if release.get("inputs", {}).get("availability_plan", {}) != source_item:
        errors.append("Capture-plan source binding differs from V8 release")

    source_rows = validate_population(release, availability, errors)
    expected = [row for row in source_rows if row.get("available") is True]
    planned = list(plan.get("results", []))
    if plan.get("source_candidate_count") != 115:
        errors.append("Capture-plan source count is not exactly 115")
    if len(planned) != len(expected) or plan.get("planned_capture_count") != len(planned):
        errors.append("Capture-plan count does not equal all available V8 rows")
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

    ids = [str(row.get("availability_plan_id")) for row in planned]
    targets = [str(row.get("capture_path")) for row in planned]
    if len(ids) != len(set(ids)) or len(targets) != len(set(targets)):
        errors.append("Capture plan contains duplicate IDs or targets")
    raw_root = Path(str(plan.get("raw_root", ""))).resolve()
    capture_root = Path(str(plan.get("capture_root", ""))).resolve()
    if raw_root not in capture_root.parents:
        errors.append("Capture root escaped raw root")
    for target in targets:
        if capture_root not in Path(target).resolve().parents:
            errors.append(f"Capture target escaped capture root: {target}")
        if Path(target).exists():
            errors.append(f"Immutable capture target already exists: {target}")
    counts = Counter(str(row.get("cohort")) for row in planned)
    if set(counts) - EXPECTED_COHORTS:
        errors.append("Capture plan contains an unexpected cohort")
    if dict(counts) != plan.get("planned_by_cohort"):
        errors.append("Capture-plan cohort aggregate mismatch")
    unavailable = sum(row.get("available") is False for row in source_rows)
    if plan.get("unavailable_candidates_not_planned") != unavailable:
        errors.append("Unavailable aggregate mismatch")
    unresolved_ids = [
        str(row.get("availability_plan_id")) for row in source_rows if row.get("error") is not None
    ]
    if plan.get("unresolved_candidates_quarantined") != len(unresolved_ids):
        errors.append("Unresolved quarantine count mismatch")
    if plan.get("ordered_quarantined_availability_plan_ids") != unresolved_ids:
        errors.append("Unresolved quarantine identity/order mismatch")

    complete_recompute = not any(
        token in error.casefold()
        for error in errors
        for token in ("unresolved", "aggregate mismatch", "population", "source/result mismatch")
    )
    exact_order = (
        len(planned) == len(expected)
        and not any("availability/plan mismatch" in error.casefold() for error in errors)
    )
    return {
        "verification_id": PLAN_QA_ID,
        "status": PLAN_QA_STATUS if not errors else "FAIL",
        "plan": {"path": str(plan_path.resolve()), "sha256": observed_hash},
        "checks": {
            "availability_generation": "v8",
            "availability_hash_verified": not any("availability result hash" in error.casefold() for error in errors),
            "availability_qa_hash_verified": not any("independent qa hash" in error.casefold() for error in errors),
            "source_plan_hash_verified": not any("source plan hash" in error.casefold() for error in errors),
            "complete_115_row_population_recomputed": complete_recompute,
            "all_and_only_available_rows_planned_in_order": exact_order,
            "unresolved_rows_quarantined_in_original_order": (
                plan.get("ordered_quarantined_availability_plan_ids") == unresolved_ids
            ),
            "unresolved_quarantine_count": len(unresolved_ids),
            "planned_capture_count": len(planned),
            "planned_by_cohort": dict(counts),
            "raw_replay_modifier_used": all(
                "id_/" in str(row.get("requested_archive_url")) for row in planned
            ),
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
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    if args.output.exists() or partial.exists():
        raise FileExistsError("Refusing to overwrite capture-plan V5 QA")
    result = verify(args.plan, args.plan_sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
