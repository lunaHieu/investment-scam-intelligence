"""Verify the frozen exact-68 unresolved-only ready-channel CDX release."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


RELEASE_ID = "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_CDX_BULK_RELEASE_V1"
PASS_STATUS = "PASS_FROZEN_EXACT_68_UNRESOLVED_ONLY_CDX_METADATA_RELEASE"


def _path(root: Path, item: dict[str, Any]) -> Path:
    value = Path(item["path"])
    return value if value.is_absolute() or item.get("absolute") else root / value


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def target_rows(release_path: Path) -> list[dict[str, Any]]:
    release = load_object(release_path)
    root = release_path.resolve().parents[1]
    source = _path(root, release["inputs"]["source_plan"])
    rows = _jsonl(source)
    excluded = set(release["population_contract"]["excluded_availability_plan_ids"])
    return [row for row in rows if row["availability_plan_id"] not in excluded]


def verify(release_path: Path, *, require_output_absent: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    release = load_object(release_path)
    root = release_path.resolve().parents[1]
    if release.get("release_id") != RELEASE_ID or release.get("status") != "FROZEN_EXACT_68_UNRESOLVED_ONLY_METADATA_RELEASE_SEPARATE_EXECUTION":
        errors.append("Unexpected bulk CDX release identity/status")
    for item in release.get("basis", []):
        path = _path(root, item)
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            errors.append(f"Basis hash mismatch: {item.get('role')}")
    for role, item in release.get("inputs", {}).items():
        path = _path(root, item)
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            errors.append(f"Input hash mismatch: {role}")

    plan = _jsonl(_path(root, release["inputs"]["source_plan"]))
    population = release.get("population_contract", {})
    excluded = population.get("excluded_availability_plan_ids")
    if len(plan) != 70 or [row.get("availability_plan_id") for row in plan] != [f"TTCV1_B3_AVAIL_{i:03d}" for i in range(1, 71)]:
        errors.append("Source plan is not the frozen exact-70 ordered population")
    if excluded != ["TTCV1_B3_AVAIL_001", "TTCV1_B3_AVAIL_002"]:
        errors.append("Bulk exclusions are not exactly quarantine row 001 and resolved canary row 002")
    rows = [row for row in plan if row.get("availability_plan_id") not in set(excluded or [])]
    expected_ids = [f"TTCV1_B3_AVAIL_{i:03d}" for i in range(3, 71)]
    if [row.get("availability_plan_id") for row in rows] != expected_ids:
        errors.append("Bulk target membership/order is not exact unresolved-only 003..070")
    if len(rows) != 68 or sum(row.get("cohort") == "DEVELOPMENT" for row in rows) != 48 or sum(row.get("cohort") == "EXTERNAL_HOLDOUT" for row in rows) != 20:
        errors.append("Bulk target cohort counts changed")
    channels = {name: sum(row.get("channel_id") == name for row in rows) for name in {row.get("channel_id") for row in rows}}
    if channels != {"CONFIRMED_REGULATOR_LINKED_WEBSITE": 33, "LEGITIMATE_REGISTER_LINKED_WEBSITE": 35}:
        errors.append("Bulk target channel counts changed")

    canary_report = load_object(_path(root, release["inputs"]["canary_report"]))
    canary_qa = load_object(_path(root, release["inputs"]["canary_result_qa"]))
    if canary_report.get("status") not in {"COMPLETE_VALID_CDX_CANARY_WITH_ELIGIBLE_METADATA", "COMPLETE_VALID_CDX_CANARY_EMPTY_NO_ELIGIBLE_SNAPSHOT"}:
        errors.append("Canary is not a terminal valid JSON result")
    if canary_report.get("target_availability_plan_id") != "TTCV1_B3_AVAIL_002" or canary_report.get("network_request_count") != 1:
        errors.append("Canary target/request identity changed")
    if canary_qa.get("status") != "PASS_CDX_CANARY_VALID_BULK_RELEASE_MAY_BE_PREPARED" or canary_qa.get("errors") != []:
        errors.append("Canary independent QA does not authorize bulk preparation")
    if canary_qa.get("decision", {}).get("bulk_cdx_release_may_be_prepared") is not True:
        errors.append("Canary QA bulk preparation decision changed")

    contract = release.get("cdx_contract", {})
    expected_contract = {
        "endpoint": "https://web.archive.org/cdx/search/cdx",
        "allowed_network_hosts": ["web.archive.org"],
        "minimum_delay_seconds": 60.0,
        "maximum_attempts_per_query": 1,
        "maximum_logical_requests": 68,
        "timeout_seconds": 30,
        "maximum_redirects": 0,
        "maximum_response_bytes": 2097152,
        "required_content_type_prefix": "application/json",
        "stop_on_http_429": True,
        "stop_on_any_http_or_transport_error": True,
        "partial_journal_reserved_before_network": True,
        "partial_journal_auto_resume_allowed": False,
        "output_overwrite_allowed": False,
        "archived_page_download_allowed": False,
    }
    for key, value in expected_contract.items():
        if contract.get(key) != value:
            errors.append(f"Bulk CDX contract changed: {key}")
    query = contract.get("query_template", {})
    if query.get("matchType") != "exact" or query.get("output") != "json" or query.get("fields") != ["timestamp", "original", "statuscode", "mimetype", "digest"] or query.get("filters") != ["statuscode:200", "mimetype:text/html"] or query.get("maximum_rows") != 1000:
        errors.append("Bulk CDX query template changed")

    planned = release.get("planned_output", {})
    output = Path(planned.get("path", ""))
    partial = output.with_suffix(output.suffix + planned.get("partial_journal_suffix", ".partial"))
    raw_dir = Path(planned.get("raw_response_directory", ""))
    if require_output_absent and (output.exists() or partial.exists() or raw_dir.exists()):
        errors.append("Bulk CDX final, partial or raw output already exists")
    decision = release.get("decision", {})
    for key in ("network_execution_allowed_in_preparation_run", "candidate_live_domain_access_allowed", "archived_page_download_allowed", "capture_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "model_scoring_allowed", "training_allowed"):
        if decision.get(key) is not False:
            errors.append(f"Forbidden bulk release decision opened: {key}")
    if decision.get("separate_execution_invocation_required") is not True:
        errors.append("Separate execution invocation is not required")
    return {
        "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_CDX_BULK_RELEASE_QA_V1",
        "status": PASS_STATUS if not errors else "FAIL",
        "release": {"path": str(release_path.resolve()), "sha256": sha256_file(release_path)},
        "checks": {"target_rows": len(rows), "development_rows": 48, "external_holdout_rows": 20, "confirmed_rows": 33, "legitimate_rows": 35, "first_target": expected_ids[0], "last_target": expected_ids[-1], "minimum_delay_seconds": contract.get("minimum_delay_seconds"), "maximum_network_requests": contract.get("maximum_logical_requests")},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "candidate_domain_access_operations": 0, "archived_page_downloads": 0, "captures": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--allow-existing-output", action="store_true")
    args = parser.parse_args()
    result = verify(args.release, require_output_absent=not args.allow_existing_output)
    if args.output:
        partial = args.output.with_suffix(args.output.suffix + ".partial")
        if args.output.exists() or partial.exists():
            raise FileExistsError("Refusing to overwrite bulk CDX release QA")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
