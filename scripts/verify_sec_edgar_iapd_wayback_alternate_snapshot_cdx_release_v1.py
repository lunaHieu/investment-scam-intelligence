"""Independently verify the frozen one-row alternate-snapshot CDX release."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import (
    load_object,
    sha256_file,
)


RELEASE_ID = "ISI_SEC_EDGAR_IAPD_WAYBACK_ALTERNATE_SNAPSHOT_CDX_RELEASE_V1"
PASS_STATUS = "PASS_FROZEN_ONE_ROW_ARCHIVE_METADATA_ONLY_CDX_RELEASE"
TARGET_ID = "TTCV1_EDGAR_AVAIL_DEV_037"
FAILED_TIMESTAMP = "20260210193325"
FAILED_RESPONSE_SHA256 = "1c98e3ca60f14fecc235ee47c09ec2fd61f4b3a696251174c4723024279d95e3"
EXPECTED_FIELDS = ["timestamp", "original", "statuscode", "mimetype", "digest"]
EXPECTED_OUTPUT = Path(
    r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs"
    r"\sec_edgar_iapd_alternate_snapshot_cdx_v1\cdx_enumeration_report_v1.json"
)


def verify(release_path: Path, *, require_output_absent: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    try:
        release = load_object(release_path)
    except Exception as error:
        return {
            "verification_id": "ISI_SEC_EDGAR_IAPD_ALTERNATE_SNAPSHOT_CDX_RELEASE_QA_V1",
            "status": "FAIL",
            "errors": [f"Release loading failed: {type(error).__name__}: {error}"],
        }
    root = release_path.resolve().parents[1]
    if release.get("release_id") != RELEASE_ID:
        errors.append("Unexpected alternate-snapshot CDX release identity")
    if release.get("status") != "FROZEN_OFFLINE_PREPARED_NETWORK_NOT_BEFORE_GATE":
        errors.append("Unexpected alternate-snapshot CDX release status")

    for item in release.get("basis", []):
        path = root / item["path"]
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            errors.append(f"Basis hash mismatch: {item['path']}")
    for role, item in release.get("inputs", {}).items():
        path = Path(item["path"]) if item.get("absolute", False) else root / item["path"]
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            errors.append(f"Input hash mismatch: {role}")

    result_registry = load_object(root / release["inputs"]["capture_retry_result_registry"]["path"])
    retry_report = load_object(Path(release["inputs"]["capture_retry_report"]["path"]))
    retry_qa = load_object(Path(release["inputs"]["capture_retry_qa_v2"]["path"]))
    result = result_registry.get("result", {})
    decision = result_registry.get("decision", {})
    if result_registry.get("status") != "INDEPENDENTLY_VERIFIED_REPEAT_42_BYTE_FAILURE_QUARANTINE_REMAINS":
        errors.append("Capture retry result status changed")
    if result.get("retry_id") != TARGET_ID or result.get("response_bytes") != 42:
        errors.append("Capture retry failure identity or byte count changed")
    if result.get("response_sha256") != FAILED_RESPONSE_SHA256:
        errors.append("Capture retry failed-body hash changed")
    if decision.get("another_same_snapshot_retry_allowed") is not False:
        errors.append("Same-snapshot retry is not explicitly closed")
    if decision.get("separate_alternate_snapshot_cdx_protocol_may_be_prepared_offline") is not True:
        errors.append("Offline alternate-snapshot CDX preparation is not authorized")
    if retry_report.get("status") != "INCOMPLETE_FAILURE_PRESERVED":
        errors.append("Capture retry report no longer preserves failure")
    if retry_report.get("created_at") != release.get("cooldown_contract", {}).get("prior_archive_request_created_at"):
        errors.append("Cooldown is not bound to the actual retry report created_at")
    if retry_qa.get("status") != "PASS_RETRY_FAILURE_PRESERVED_QUARANTINE_REMAINS":
        errors.append("Capture retry authoritative QA status changed")

    target = release.get("target_record", {})
    expected_target = {
        "availability_plan_id": TARGET_ID,
        "shortlist_id": "TTCV1_EDGAR_DEV_045",
        "cohort": "DEVELOPMENT",
        "candidate_host": "lionpoint.com",
        "candidate_url": "https://lionpoint.com/",
        "failed_snapshot_timestamp": FAILED_TIMESTAMP,
        "failed_requested_archive_url": (
            "https://web.archive.org/web/20260210193325id_/https://lionpoint.com/"
        ),
        "failed_response_bytes": 42,
        "failed_response_sha256": FAILED_RESPONSE_SHA256,
        "excluded_snapshot_timestamps": [FAILED_TIMESTAMP],
    }
    if target != expected_target:
        errors.append("Frozen target identity or failed-snapshot exclusion changed")

    cooldown = release.get("cooldown_contract", {})
    try:
        parent = datetime.fromisoformat(cooldown["prior_archive_request_created_at"])
        not_before = datetime.fromisoformat(cooldown["not_before"])
        created = datetime.fromisoformat(release["created_at"])
        seconds = (not_before - parent).total_seconds()
        if seconds != 86400 or cooldown.get("minimum_cooldown_seconds") != 86400:
            errors.append("CDX network gate is not exactly 24 hours after the prior archive request")
        if created < parent or created >= not_before:
            errors.append("Release was not prepared inside the offline-only window")
    except Exception as error:
        seconds = None
        errors.append(f"Invalid cooldown timestamps: {type(error).__name__}: {error}")

    contract = release.get("cdx_contract", {})
    query = contract.get("query", {})
    if contract.get("endpoint") != "https://web.archive.org/cdx/search/cdx":
        errors.append("CDX endpoint changed")
    if contract.get("allowed_network_hosts") != ["web.archive.org"]:
        errors.append("CDX host allowlist changed")
    if float(contract.get("minimum_delay_seconds", 0)) < 60.0:
        errors.append("CDX minimum pacing is below 60 seconds")
    if contract.get("maximum_logical_requests") != 1 or contract.get("maximum_attempts_per_query") != 1:
        errors.append("CDX one-request/one-attempt budget changed")
    if contract.get("stop_on_http_429") is not True or contract.get("output_overwrite_allowed") is not False:
        errors.append("CDX stop/no-overwrite contract changed")
    if query.get("url") != "lionpoint.com/" or query.get("matchType") != "exact":
        errors.append("CDX exact target query changed")
    if query.get("output") != "json" or query.get("fields") != EXPECTED_FIELDS:
        errors.append("CDX output format or field order changed")
    if query.get("filters") != ["statuscode:200", "mimetype:text/html"]:
        errors.append("CDX server-side filters changed")
    if query.get("excluded_snapshot_timestamps") != [FAILED_TIMESTAMP]:
        errors.append("CDX failed-timestamp exclusion changed")
    if query.get("maximum_rows") != 1000:
        errors.append("CDX maximum row count changed")
    if contract.get("eligible_mimetypes") != ["text/html"]:
        errors.append("CDX eligible mimetype set changed")
    if contract.get("selection_rule") != (
        "MIN_ABSOLUTE_TIME_DISTANCE_THEN_EARLIER_TIMESTAMP_THEN_ORIGINAL_THEN_DIGEST"
    ):
        errors.append("Deterministic CDX selection rule changed")

    planned = release.get("planned_output", {})
    output = Path(planned.get("path", ""))
    partial = output.with_suffix(output.suffix + ".partial")
    if output != EXPECTED_OUTPUT:
        errors.append("CDX planned output path changed")
    if planned.get("report_id") != "ISI_SEC_EDGAR_IAPD_ALTERNATE_SNAPSHOT_CDX_REPORT_V1":
        errors.append("CDX planned report identity changed")
    if require_output_absent and (output.exists() or partial.exists()):
        errors.append("CDX final or partial output already exists")

    release_decision = release.get("decision", {})
    required_false = (
        "network_execution_allowed_at_release_time",
        "candidate_live_domain_access_allowed",
        "archived_page_download_allowed",
        "artifact_capture_allowed",
        "same_failed_timestamp_allowed",
        "labeling_allowed",
        "original_review_population_mutation_allowed",
        "validation_or_test_opening_allowed",
        "model_scoring_allowed",
        "training_allowed",
    )
    for field in required_false:
        if release_decision.get(field) is not False:
            errors.append(f"Forbidden release decision is not closed: {field}")
    if release_decision.get("metadata_enumeration_allowed_after_not_before") is not True:
        errors.append("Post-gate CDX metadata enumeration is not explicitly permitted")
    if release_decision.get("selected_candidate_requires_separate_capture_release") is not True:
        errors.append("Separate capture release requirement is not explicit")

    release_hash = sha256_file(release_path)
    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_ALTERNATE_SNAPSHOT_CDX_RELEASE_QA_V1",
        "status": PASS_STATUS if not errors else "FAIL",
        "release": {"path": str(release_path.resolve()), "sha256": release_hash},
        "checks": {
            "target_rows": 1,
            "target_availability_plan_id": TARGET_ID,
            "failed_snapshot_timestamp_excluded": FAILED_TIMESTAMP,
            "failed_response_sha256_pinned": FAILED_RESPONSE_SHA256,
            "minimum_cooldown_seconds": seconds,
            "not_before": cooldown.get("not_before"),
            "maximum_logical_requests": contract.get("maximum_logical_requests"),
            "archived_page_download_allowed": False,
            "candidate_live_domain_access_allowed": False,
        },
        "errors": errors,
        "safety_contract": {
            "network_operations": 0,
            "candidate_domain_access_operations": 0,
            "archived_page_downloads": 0,
            "captures": 0,
            "labels_created": 0,
            "model_operations": 0,
            "training_allowed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.release)
    if args.output:
        partial = args.output.with_suffix(args.output.suffix + ".partial")
        if args.output.exists() or partial.exists():
            raise FileExistsError("Refusing to overwrite alternate-snapshot CDX release QA")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
