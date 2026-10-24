"""Independently verify the exact two-row V11 supplemental capture plan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.build_sec_edgar_iapd_v11_supplemental_capture_plan import (
    AVAILABILITY_QA_ID,
    AVAILABILITY_REPORT_ID,
    EXPECTED_IDS,
    PLAN_STATUS,
    QA_ID,
    QA_STATUS,
    REPORT_ID,
    build_plan,
)
from scripts.capture_balanced_wayback_plan_v2 import assert_archive_url, raw_replay_url
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import (
    load_object,
    sha256_file,
)


def verify(plan_path: Path, plan_sha256: str) -> dict[str, Any]:
    errors: list[str] = []
    try:
        observed_hash = sha256_file(plan_path)
        plan = load_object(plan_path)
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        return {"verification_id": QA_ID, "status": "FAIL", "errors": [str(error)]}
    if observed_hash != plan_sha256:
        errors.append("Supplemental plan SHA-256 mismatch")
    if (
        plan.get("report_id") != REPORT_ID
        or plan.get("status") != PLAN_STATUS
        or plan.get("tooling_version") != "v11-supplemental-v1"
        or plan.get("availability_generation") != "v11"
    ):
        errors.append("Unexpected V11 supplemental plan identity/status/generation")
    if plan.get("source_candidate_count") != 115 or plan.get("planned_capture_count") != 2:
        errors.append("Supplemental plan population is not 115 source rows and two planned rows")
    if plan.get("ordered_supplemental_ids") != list(EXPECTED_IDS):
        errors.append("Supplemental identity/order contract changed")
    if plan.get("frozen_original_capture_plan_mutated") is not False:
        errors.append("Frozen original capture plan mutation flag changed")

    source_item = plan.get("source_plan", {})
    availability_item = plan.get("availability_result", {})
    qa_item = plan.get("independent_availability_qa", {})
    source_path = Path(str(source_item.get("path", "")))
    availability_path = Path(str(availability_item.get("path", "")))
    availability_qa_path = Path(str(qa_item.get("path", "")))
    for label, path, expected in (
        ("source plan", source_path, source_item.get("sha256")),
        ("availability result", availability_path, availability_item.get("sha256")),
        ("availability QA", availability_qa_path, qa_item.get("sha256")),
    ):
        try:
            if sha256_file(path) != expected:
                errors.append(f"Supplemental {label} hash mismatch")
        except (FileNotFoundError, OSError):
            errors.append(f"Supplemental {label} is missing")
    try:
        availability = load_object(availability_path)
        availability_qa = load_object(availability_qa_path)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        availability, availability_qa = {}, {}
        errors.append(f"Cannot read V11 availability evidence: {error}")
    if availability.get("report_id") != AVAILABILITY_REPORT_ID:
        errors.append("V11 availability report identity changed")
    if availability.get("status") != "COMPLETE" or availability.get("unresolved_error_count") != 0:
        errors.append("V11 availability result is not complete")
    if availability_qa.get("verification_id") != AVAILABILITY_QA_ID:
        errors.append("V11 availability QA identity changed")
    if availability_qa.get("status") != qa_item.get("required_status"):
        errors.append("V11 availability QA status binding changed")
    if availability_item.get("report_id") != availability.get("report_id"):
        errors.append("V11 availability result identity binding changed")
    if availability_item.get("created_at") != availability.get("created_at"):
        errors.append("V11 availability created_at binding changed")

    planned = list(plan.get("results", []))
    planned_ids = [str(row.get("availability_plan_id")) for row in planned]
    if planned_ids != list(EXPECTED_IDS):
        errors.append("Planned rows are not exactly the two expected V11 IDs")
    for index, row in enumerate(planned):
        if row.get("cohort") != "EXTERNAL_HOLDOUT":
            errors.append(f"Unexpected cohort at row {index}")
        if row.get("archived_page_downloaded") is not False or row.get("artifact_captured") is not False:
            errors.append(f"Supplemental plan opens capture state at row {index}")
        try:
            replay_url, timestamp = raw_replay_url(str(row["snapshot_url"]))
            assert_archive_url(str(row["requested_archive_url"]))
            if replay_url != row.get("requested_archive_url") or timestamp != row.get("snapshot_timestamp"):
                errors.append(f"Raw replay binding mismatch at row {index}")
            if "id_/" not in str(row.get("requested_archive_url")):
                errors.append(f"Raw replay modifier missing at row {index}")
        except (KeyError, ValueError) as error:
            errors.append(f"Invalid supplemental archive URL at row {index}: {error}")
        target = Path(str(row.get("capture_path", ""))).resolve()
        capture_root = Path(str(plan.get("capture_root", ""))).resolve()
        if capture_root not in target.parents:
            errors.append(f"Supplemental target escaped capture root at row {index}")
        if target.exists():
            errors.append(f"Supplemental immutable target already exists at row {index}")

    raw_root = Path(str(plan.get("raw_root", ""))).resolve()
    capture_root = Path(str(plan.get("capture_root", ""))).resolve()
    if raw_root not in capture_root.parents:
        errors.append("Supplemental capture root escaped raw root")
    safety = plan.get("safety_contract", {})
    if any(safety.get(field) != 0 for field in (
        "network_operations", "candidate_live_domain_access_operations",
        "archived_page_download_operations", "candidate_artifact_captures",
        "labels_created", "model_operations",
    )) or safety.get("training_allowed") is not False:
        errors.append("Supplemental plan safety contract changed")

    return {
        "verification_id": QA_ID,
        "status": QA_STATUS if not errors else "FAIL",
        "plan": {"path": str(plan_path.resolve()), "sha256": observed_hash},
        "checks": {
            "source_population_115": plan.get("source_candidate_count") == 115,
            "exact_two_row_membership_and_order": planned_ids == list(EXPECTED_IDS),
            "external_holdout_cohort_preserved": all(row.get("cohort") == "EXTERNAL_HOLDOUT" for row in planned),
            "availability_generation": "v11",
            "availability_hash_verified": not any("availability result hash" in e.casefold() for e in errors),
            "availability_qa_hash_verified": not any("availability qa hash" in e.casefold() for e in errors),
            "raw_replay_modifier_used": all("id_/" in str(row.get("requested_archive_url")) for row in planned),
            "capture_targets_absent": all(not Path(str(row.get("capture_path", ""))).exists() for row in planned),
        },
        "decision": {
            "capture_plan_qa_passed": not errors,
            "capture_execution_release_may_be_prepared": not errors,
            "archived_page_download_allowed_by_this_qa": False,
            "candidate_live_domain_access_allowed": False,
            "labeling_allowed": False,
            "validation_or_test_opening_allowed": False,
            "training_allowed": False,
        },
        "errors": errors,
        "safety_contract": {"network_operations": 0, "captures": 0, "labels": 0, "model": 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite V11 supplemental plan QA")
    result = verify(args.plan, args.plan_sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
