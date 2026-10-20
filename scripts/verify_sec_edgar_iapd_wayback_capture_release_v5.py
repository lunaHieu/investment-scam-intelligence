"""Independently verify a partial-resolved V8 capture release V5."""

from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

from scripts.build_sec_edgar_iapd_wayback_capture_plan_v5 import (
    AVAILABILITY_REPORT_ID,
    PLAN_QA_ID,
    PLAN_QA_STATUS,
    PLAN_STATUS,
    REPORT_ID as PLAN_REPORT_ID,
)
from scripts.build_sec_edgar_iapd_wayback_capture_release_v5 import (
    MINIMUM_COOLDOWN_SECONDS,
    RELEASE_ID,
    RELEASE_QA_ID,
    RELEASE_QA_STATUS,
    parse_time,
)
from scripts.capture_balanced_wayback_plan_v2 import assert_archive_url
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


EXPECTED_EXECUTION_CONTRACT = {
    "allowed_network_hosts": ["web.archive.org"],
    "minimum_delay_seconds": 30.0,
    "maximum_attempts_per_snapshot": 1,
    "timeout_seconds": 30,
    "maximum_redirects": 3,
    "maximum_response_bytes": 26214400,
    "required_content_type_prefix": "text/html",
    "https_only": True,
    "raw_replay_modifier_required": True,
    "automatic_external_redirect_following": False,
    "stop_on_http_429": True,
    "errors_are_preserved": True,
    "failed_rows_are_not_replaced": True,
    "output_overwrite_allowed": False,
}


def verify(release_path: Path) -> dict[str, Any]:
    release = load_object(release_path)
    errors: list[str] = []
    if release.get("release_id") != RELEASE_ID or release.get("tooling_version") != "v5":
        errors.append("Unexpected capture-release V5 identity or tooling version")
    inputs = release.get("inputs", {})
    plan_item = inputs.get("capture_plan", {})
    qa_item = inputs.get("independent_capture_plan_qa", {})
    availability_item = inputs.get("final_availability_result", {})
    plan_path = Path(str(plan_item.get("path", "")))
    qa_path = Path(str(qa_item.get("path", "")))
    availability_path = Path(str(availability_item.get("path", "")))
    try:
        if sha256_file(plan_path) != plan_item.get("sha256"):
            errors.append("Capture plan hash mismatch")
        if sha256_file(qa_path) != qa_item.get("sha256"):
            errors.append("Capture plan QA hash mismatch")
        if sha256_file(availability_path) != availability_item.get("sha256"):
            errors.append("Final V8 availability result hash mismatch")
        plan = load_object(plan_path)
        qa = load_object(qa_path)
        availability = load_object(availability_path)
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError) as error:
        plan, qa, availability = {}, {}, {}
        errors.append(f"Cannot read V5 release evidence: {error}")

    if (
        plan.get("report_id") != PLAN_REPORT_ID
        or plan.get("status") != PLAN_STATUS
        or plan.get("tooling_version") != "v5"
        or plan.get("availability_generation") != "v8"
    ):
        errors.append("Unexpected V8-derived capture-plan V5 identity")
    plan_availability = plan.get("availability_result", {})
    expected_availability_item = {
        "generation": "v8",
        "path": str(availability_path.resolve()),
        "sha256": plan_availability.get("sha256"),
        "report_id": AVAILABILITY_REPORT_ID,
        "created_at": plan_availability.get("created_at"),
    }
    if availability_item != expected_availability_item:
        errors.append("Release/plan final V8 availability binding mismatch")
    if availability.get("report_id") != AVAILABILITY_REPORT_ID:
        errors.append("Final V8 availability identity changed")
    if availability.get("created_at") != availability_item.get("created_at"):
        errors.append("Final V8 availability timestamp changed")
    if availability.get("status") != "INCOMPLETE_ERRORS_PRESERVED" or availability.get("unresolved_error_count") != 2:
        errors.append("V8 availability result is not the exact verified two-row partial")
    if availability.get("capture_plan_construction_ready") is not False:
        errors.append("V8 partial readiness flag changed")
    if qa_item.get("verification_id") != PLAN_QA_ID or qa_item.get("required_status") != PLAN_QA_STATUS:
        errors.append("Capture-plan V5 QA input contract changed")
    if qa.get("verification_id") != PLAN_QA_ID or qa.get("status") != PLAN_QA_STATUS:
        errors.append("Capture-plan independent V5 QA did not pass")
    if qa.get("plan", {}).get("sha256") != plan_item.get("sha256"):
        errors.append("Capture-plan V5 QA hash binding mismatch")
    if qa.get("checks", {}).get("availability_generation") != "v8":
        errors.append("Capture-plan V5 QA generation binding mismatch")
    if qa.get("checks", {}).get("complete_115_row_population_recomputed") is not True:
        errors.append("Capture-plan V5 QA did not recompute all 115 rows")
    if qa.get("checks", {}).get("all_and_only_available_rows_planned_in_order") is not True:
        errors.append("Capture-plan V5 QA did not prove exact available membership/order")
    if qa.get("checks", {}).get("unresolved_rows_quarantined_in_original_order") is not True:
        errors.append("Capture-plan V5 QA did not prove unresolved quarantine order")
    if qa.get("decision", {}).get("capture_execution_release_may_be_prepared") is not True:
        errors.append("Capture-plan V5 QA release decision changed")
    if (
        plan_item.get("record_count") != plan.get("planned_capture_count")
        or int(plan.get("planned_capture_count", 0)) < 1
        or plan.get("source_candidate_count") != 115
    ):
        errors.append("Capture release population/count binding mismatch")

    cooldown = release.get("cooldown_contract", {})
    contract = release.get("execution_contract", {})
    try:
        availability_time = parse_time(str(availability_item.get("created_at")))
        release_time = parse_time(str(release.get("created_at")))
        gate_time = parse_time(str(contract.get("not_before")))
        required_time = availability_time + timedelta(seconds=MINIMUM_COOLDOWN_SECONDS)
        if gate_time < required_time:
            errors.append("Capture not-before is less than 24 hours after final availability")
        if gate_time < release_time:
            errors.append("Capture not-before predates release creation")
        expected_cooldown = {
            "availability_generation": "v8",
            "final_availability_created_at": availability_item.get("created_at"),
            "minimum_cooldown_seconds": MINIMUM_COOLDOWN_SECONDS,
            "required_not_before": required_time.isoformat(),
            "not_before": contract.get("not_before"),
        }
        if cooldown != expected_cooldown:
            errors.append("Capture cooldown contract changed")
    except (TypeError, ValueError):
        errors.append("Capture-release V5 timestamps are invalid")
    if contract.get("not_before") != cooldown.get("not_before"):
        errors.append("Execution/cooldown not-before mismatch")
    for key, expected in EXPECTED_EXECUTION_CONTRACT.items():
        if contract.get(key) != expected:
            errors.append(f"Capture execution contract changed: {key}")
    for index, row in enumerate(plan.get("results", [])):
        try:
            assert_archive_url(str(row["requested_archive_url"]))
            if "id_/" not in str(row["requested_archive_url"]):
                errors.append(f"Raw replay modifier missing at row {index}")
        except (KeyError, ValueError) as error:
            errors.append(f"Invalid archive request at row {index}: {error}")

    planned_output = release.get("planned_output", {})
    report_path = Path(str(planned_output.get("path", "")))
    if planned_output.get("report_id") != "ISI_SEC_EDGAR_IAPD_WAYBACK_CAPTURE_REPORT_V1":
        errors.append("Unexpected planned capture report identity")
    if report_path.exists() or report_path.with_suffix(report_path.suffix + ".partial").exists():
        errors.append("Capture report target already exists")
    decision = release.get("decision", {})
    if decision.get("archive_only_capture_allowed_at_or_after_not_before") is not True:
        errors.append("Archive-only capture gate is not open after not-before")
    for gate in (
        "candidate_live_domain_access_allowed", "text_extraction_allowed", "labeling_allowed",
        "validation_or_test_opening_allowed", "training_allowed",
    ):
        if decision.get(gate) is not False:
            errors.append(f"Forbidden release gate opened: {gate}")

    return {
        "verification_id": RELEASE_QA_ID,
        "status": RELEASE_QA_STATUS if not errors else "FAIL",
        "release": {"path": str(release_path.resolve()), "sha256": sha256_file(release_path)},
        "checks": {
            "plan_hash_verified": not any("plan hash" in error.casefold() for error in errors),
            "plan_qa_hash_verified": not any("qa hash" in error.casefold() for error in errors),
            "availability_hash_verified": not any("availability result hash" in error.casefold() for error in errors),
            "availability_generation": "v8",
            "source_candidate_count": plan.get("source_candidate_count"),
            "record_count": plan.get("planned_capture_count"),
            "minimum_cooldown_seconds": cooldown.get("minimum_cooldown_seconds"),
            "not_before": contract.get("not_before"),
            "minimum_delay_seconds": contract.get("minimum_delay_seconds"),
            "maximum_attempts_per_snapshot": contract.get("maximum_attempts_per_snapshot"),
            "stop_on_http_429": contract.get("stop_on_http_429"),
            "output_overwrite_allowed": contract.get("output_overwrite_allowed"),
            "archive_host_only": contract.get("allowed_network_hosts") == ["web.archive.org"],
            "raw_replay_modifier_used": all(
                "id_/" in str(row.get("requested_archive_url")) for row in plan.get("results", [])
            ),
            "planned_output_absent": (
                not report_path.exists()
                and not report_path.with_suffix(report_path.suffix + ".partial").exists()
            ),
        },
        "decision": {
            "release_qa_passed": not errors,
            "execution_allowed_at_or_after_not_before": not errors,
            "candidate_live_domain_access_allowed": False,
            "text_extraction_allowed": False,
            "labeling_allowed": False,
            "training_allowed": False,
        },
        "errors": errors,
        "safety_contract": {"network_operations": 0, "captures": 0, "labels": 0, "model": 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    if args.output.exists() or partial.exists():
        raise FileExistsError("Refusing to overwrite capture-release V5 QA")
    result = verify(args.release)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
