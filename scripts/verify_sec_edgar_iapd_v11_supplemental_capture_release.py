"""Independently verify the V11 supplemental archive-only capture release."""

from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

from scripts.build_sec_edgar_iapd_v11_supplemental_capture_plan import (
    AVAILABILITY_REPORT_ID,
    EXPECTED_IDS,
    PLAN_STATUS,
    QA_ID,
    QA_STATUS,
    REPORT_ID as PLAN_REPORT_ID,
)
from scripts.build_sec_edgar_iapd_v11_supplemental_capture_release import (
    MINIMUM_COOLDOWN_SECONDS,
    RELEASE_ID,
    RELEASE_QA_ID,
    RELEASE_QA_STATUS,
    parse_time,
)
from scripts.capture_balanced_wayback_plan_v2 import assert_archive_url
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import (
    load_object,
    sha256_file,
)


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
    "partial_journal_reserved_before_network": True,
    "automatic_resume_allowed": False,
}


def verify(release_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        release = load_object(release_path)
        release_hash = sha256_file(release_path)
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        return {"verification_id": RELEASE_QA_ID, "status": "FAIL", "errors": [str(error)]}
    if release.get("release_id") != RELEASE_ID or release.get("tooling_version") != "v11-supplemental-v1":
        errors.append("Unexpected V11 supplemental release identity/tooling version")
    inputs = release.get("inputs", {})
    plan_item = inputs.get("capture_plan", {})
    plan_qa_item = inputs.get("independent_capture_plan_qa", {})
    availability_item = inputs.get("final_v11_availability_result", {})
    availability_qa_item = inputs.get("independent_v11_availability_qa", {})
    paths = {
        "plan": Path(str(plan_item.get("path", ""))),
        "plan_qa": Path(str(plan_qa_item.get("path", ""))),
        "availability": Path(str(availability_item.get("path", ""))),
        "availability_qa": Path(str(availability_qa_item.get("path", ""))),
    }
    for key, item in (
        ("plan", plan_item), ("plan_qa", plan_qa_item),
        ("availability", availability_item), ("availability_qa", availability_qa_item),
    ):
        try:
            if sha256_file(paths[key]) != item.get("sha256"):
                errors.append(f"{key} hash mismatch")
        except (FileNotFoundError, OSError):
            errors.append(f"{key} evidence missing")
    try:
        plan = load_object(paths["plan"])
        plan_qa = load_object(paths["plan_qa"])
        availability = load_object(paths["availability"])
        availability_qa = load_object(paths["availability_qa"])
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        plan, plan_qa, availability, availability_qa = {}, {}, {}, {}
        errors.append(f"Cannot read V11 supplemental release evidence: {error}")

    if (
        plan.get("report_id") != PLAN_REPORT_ID
        or plan.get("status") != PLAN_STATUS
        or plan.get("tooling_version") != "v11-supplemental-v1"
        or plan.get("availability_generation") != "v11"
    ):
        errors.append("Unexpected supplemental plan binding")
    if plan.get("planned_capture_count") != 2 or plan.get("ordered_supplemental_ids") != list(EXPECTED_IDS):
        errors.append("Supplemental plan count/order binding changed")
    if plan_qa.get("verification_id") != QA_ID or plan_qa.get("status") != QA_STATUS:
        errors.append("Supplemental plan QA did not pass")
    if plan_qa.get("plan", {}).get("sha256") != plan_item.get("sha256"):
        errors.append("Supplemental plan QA hash binding changed")
    if availability.get("report_id") != AVAILABILITY_REPORT_ID or availability.get("status") != "COMPLETE":
        errors.append("V11 availability result is not complete")
    if availability_qa.get("inputs", {}).get("report_sha256") != availability_item.get("sha256"):
        errors.append("V11 availability QA/result binding changed")
    if availability_item.get("created_at") != availability.get("created_at"):
        errors.append("V11 availability created_at binding changed")
    if availability_item.get("report_id") != availability.get("report_id"):
        errors.append("V11 availability report identity binding changed")

    identity_contract = release.get("supplemental_identity_contract", {})
    if identity_contract.get("ordered_availability_plan_ids") != list(EXPECTED_IDS):
        errors.append("Supplemental release identity order changed")
    if identity_contract.get("cohort") != "EXTERNAL_HOLDOUT":
        errors.append("Supplemental release cohort changed")
    for key in ("original_58_row_capture_plan_mutation_allowed", "original_56_row_review_population_mutation_allowed"):
        if identity_contract.get(key) is not False:
            errors.append(f"Forbidden historical mutation gate opened: {key}")

    cooldown = release.get("cooldown_contract", {})
    contract = release.get("execution_contract", {})
    try:
        availability_time = parse_time(str(availability_item.get("created_at")))
        release_time = parse_time(str(release.get("created_at")))
        gate_time = parse_time(str(contract.get("not_before")))
        required_time = availability_time + timedelta(seconds=MINIMUM_COOLDOWN_SECONDS)
        if gate_time < required_time:
            errors.append("not-before is less than 24 hours after V11 availability")
        if gate_time < release_time:
            errors.append("not-before predates release creation")
        expected_cooldown = {
            "availability_generation": "v11",
            "final_availability_created_at": availability_item.get("created_at"),
            "minimum_cooldown_seconds": MINIMUM_COOLDOWN_SECONDS,
            "required_not_before": required_time.isoformat(),
            "not_before": contract.get("not_before"),
        }
        if cooldown != expected_cooldown:
            errors.append("Supplemental cooldown contract changed")
    except (TypeError, ValueError):
        errors.append("Supplemental release timestamps are invalid")
    if contract.get("not_before") != cooldown.get("not_before"):
        errors.append("Execution/cooldown not-before mismatch")
    for key, expected in EXPECTED_EXECUTION_CONTRACT.items():
        if contract.get(key) != expected:
            errors.append(f"Execution contract changed: {key}")
    for index, row in enumerate(plan.get("results", [])):
        try:
            assert_archive_url(str(row["requested_archive_url"]))
            if "id_/" not in str(row["requested_archive_url"]):
                errors.append(f"Raw replay modifier missing at row {index}")
        except (KeyError, ValueError) as error:
            errors.append(f"Invalid archive request at row {index}: {error}")

    planned_output = release.get("planned_output", {})
    report_path = Path(str(planned_output.get("path", "")))
    if planned_output.get("report_id") != "ISI_SEC_EDGAR_IAPD_V11_SUPPLEMENTAL_CAPTURE_REPORT_V1":
        errors.append("Unexpected supplemental capture report identity")
    if report_path.exists() or report_path.with_suffix(report_path.suffix + ".partial").exists():
        errors.append("Supplemental capture report target already exists")
    decision = release.get("decision", {})
    if decision.get("archive_only_capture_allowed_at_or_after_not_before") is not True:
        errors.append("Archive-only supplemental capture gate is not correctly declared")
    for gate in ("candidate_live_domain_access_allowed", "text_extraction_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "training_allowed"):
        if decision.get(gate) is not False:
            errors.append(f"Forbidden gate opened: {gate}")

    return {
        "verification_id": RELEASE_QA_ID,
        "status": RELEASE_QA_STATUS if not errors else "FAIL",
        "release": {"path": str(release_path.resolve()), "sha256": release_hash},
        "checks": {
            "plan_hash_verified": not any("plan hash" in e.casefold() for e in errors),
            "plan_qa_hash_verified": not any("plan qa hash" in e.casefold() for e in errors),
            "availability_hash_verified": not any("availability hash" in e.casefold() for e in errors),
            "availability_generation": "v11",
            "record_count": plan.get("planned_capture_count"),
            "exact_two_row_identity_order": plan.get("ordered_supplemental_ids") == list(EXPECTED_IDS),
            "minimum_cooldown_seconds": cooldown.get("minimum_cooldown_seconds"),
            "not_before": contract.get("not_before"),
            "minimum_delay_seconds": contract.get("minimum_delay_seconds"),
            "maximum_attempts_per_snapshot": contract.get("maximum_attempts_per_snapshot"),
            "stop_on_http_429": contract.get("stop_on_http_429"),
            "output_overwrite_allowed": contract.get("output_overwrite_allowed"),
            "archive_host_only": contract.get("allowed_network_hosts") == ["web.archive.org"],
            "planned_output_absent": not report_path.exists() and not report_path.with_suffix(report_path.suffix + ".partial").exists(),
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
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite V11 supplemental release QA")
    result = verify(args.release)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
