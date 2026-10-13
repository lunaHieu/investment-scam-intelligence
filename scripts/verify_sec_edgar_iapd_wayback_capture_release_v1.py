"""Independently verify a SEC/IAPD archive-only capture release."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.build_sec_edgar_iapd_wayback_capture_plan_v1 import REPORT_ID as PLAN_REPORT_ID
from scripts.build_sec_edgar_iapd_wayback_capture_release_v1 import PLAN_QA_STATUS, RELEASE_ID, parse_time
from scripts.capture_balanced_wayback_plan_v2 import assert_archive_url
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def verify(release_path: Path) -> dict[str, Any]:
    release = load_object(release_path)
    errors: list[str] = []
    if release.get("release_id") != RELEASE_ID:
        errors.append("Unexpected capture release identity")
    plan_path = Path(str(release.get("inputs", {}).get("capture_plan", {}).get("path", "")))
    qa_path = Path(str(release.get("inputs", {}).get("independent_capture_plan_qa", {}).get("path", "")))
    try:
        if sha256_file(plan_path) != release["inputs"]["capture_plan"]["sha256"]:
            errors.append("Capture plan hash mismatch")
        if sha256_file(qa_path) != release["inputs"]["independent_capture_plan_qa"]["sha256"]:
            errors.append("Capture plan QA hash mismatch")
        plan = load_object(plan_path)
        qa = load_object(qa_path)
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError) as error:
        plan, qa = {}, {}
        errors.append(f"Cannot read release evidence: {error}")
    if plan.get("report_id") != PLAN_REPORT_ID:
        errors.append("Unexpected capture plan identity")
    if qa.get("status") != PLAN_QA_STATUS or qa.get("plan", {}).get("sha256") != release.get("inputs", {}).get("capture_plan", {}).get("sha256"):
        errors.append("Capture plan QA status or binding mismatch")
    if release.get("inputs", {}).get("capture_plan", {}).get("record_count") != plan.get("planned_capture_count"):
        errors.append("Capture release record count mismatch")
    contract = release.get("execution_contract", {})
    try:
        parse_time(str(contract.get("not_before")))
    except (TypeError, ValueError):
        errors.append("Capture release not-before is invalid")
    expected_contract = {
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
    for key, expected in expected_contract.items():
        if contract.get(key) != expected:
            errors.append(f"Capture execution contract changed: {key}")
    for index, row in enumerate(plan.get("results", [])):
        try:
            assert_archive_url(str(row["requested_archive_url"]))
            if "id_/" not in str(row["requested_archive_url"]):
                errors.append(f"Raw replay modifier missing at row {index}")
        except (KeyError, ValueError) as error:
            errors.append(f"Invalid archive request at row {index}: {error}")
    decision = release.get("decision", {})
    if decision.get("archive_only_capture_allowed_at_or_after_not_before") is not True:
        errors.append("Archive-only capture gate is not open after not-before")
    for gate in ("candidate_live_domain_access_allowed", "text_extraction_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "training_allowed"):
        if decision.get(gate) is not False:
            errors.append(f"Forbidden release gate opened: {gate}")
    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_CAPTURE_RELEASE_INDEPENDENT_QA_V1",
        "status": "PASS_ARCHIVE_ONLY_CAPTURE_RELEASE" if not errors else "FAIL",
        "release": {"path": str(release_path.resolve()), "sha256": sha256_file(release_path)},
        "checks": {
            "plan_hash_verified": not any("plan hash" in error for error in errors),
            "plan_qa_hash_verified": not any("QA hash" in error for error in errors),
            "record_count": plan.get("planned_capture_count"),
            "minimum_delay_seconds": contract.get("minimum_delay_seconds"),
            "archive_host_only": contract.get("allowed_network_hosts") == ["web.archive.org"],
            "raw_replay_modifier_used": all("id_/" in str(row.get("requested_archive_url")) for row in plan.get("results", [])),
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
        raise FileExistsError("Refusing to overwrite capture release QA")
    result = verify(args.release)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
