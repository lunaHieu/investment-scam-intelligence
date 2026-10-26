"""Verify the conditional CDX metadata fallback protocol for B5."""

from __future__ import annotations

import argparse
import json
import urllib.parse
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_ready_channel_wayback_availability_continuation_release_v1 import PASS_STATUS as CONTINUATION_PASS_STATUS, continuation_plan, read_plan, verify as verify_continuation
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


PROTOCOL_ID = "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_ARCHIVE_ALTERNATIVE_ACQUISITION_PROTOCOL_V1"
QA_ID = "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_ARCHIVE_ALTERNATIVE_ACQUISITION_PROTOCOL_QA_V1"
PASS_STATUS = "PASS_CONDITIONAL_CDX_METADATA_FALLBACK_PREPARED_NETWORK_CLOSED"


def _resolve(root: Path, item: dict[str, Any]) -> Path:
    path = Path(str(item.get("path", "")))
    return path if path.is_absolute() else root / path


def verify(protocol_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        protocol = load_object(protocol_path)
    except Exception as error:
        return {"verification_id": QA_ID, "status": "FAIL", "errors": [f"Protocol load failed: {type(error).__name__}: {error}"]}
    root = protocol_path.resolve().parents[1]
    if protocol.get("protocol_id") != PROTOCOL_ID or protocol.get("status") != "FROZEN_OFFLINE_CONDITIONAL_FALLBACK_NETWORK_CLOSED":
        errors.append("Unexpected alternative-acquisition protocol identity/status")
    paths: dict[str, Path] = {}
    for role, item in protocol.get("inputs", {}).items():
        path = _resolve(root, item)
        paths[role] = path
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            errors.append(f"Alternative-acquisition input hash mismatch: {role}")
    for item in protocol.get("authoritative_components", []):
        path = _resolve(root, item)
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            errors.append(f"Alternative-acquisition component hash mismatch: {item.get('role')}")

    continuation_path = paths.get("continuation_release", Path())
    if continuation_path.is_file():
        checked = verify_continuation(continuation_path, require_output_absent=False)
        if checked.get("status") != CONTINUATION_PASS_STATUS or checked.get("errors"):
            errors.append("Continuation release no longer verifies")
        release = load_object(continuation_path)
        source = read_plan(paths["source_plan"])
        remaining = continuation_plan(release, source)
    else:
        remaining = []
    population = protocol.get("population_contract", {})
    if len(remaining) != 69 or [row.get("availability_plan_id") for row in remaining] != [f"TTCV1_B3_AVAIL_{index:03d}" for index in range(2, 71)]:
        errors.append("Alternative-acquisition continuation population changed")
    if population.get("permanently_quarantined_availability_plan_ids") != ["TTCV1_B3_AVAIL_001"] or population.get("continuation_rows") != 69 or population.get("original_order_required") is not True:
        errors.append("Alternative-acquisition population contract changed")

    activation = protocol.get("activation_contract", {})
    expected_activation = {"continuation_must_execute_first": True, "continuation_final_report_required": True, "continuation_independent_result_qa_required": True, "activation_requires_availability_endpoint_error": True, "activation_on_complete_continuation_forbidden": True, "network_operations_during_protocol_preparation": 0}
    for field, value in expected_activation.items():
        if activation.get(field) != value:
            errors.append(f"Alternative-acquisition activation contract changed: {field}")
    if activation.get("allowed_activation_statuses") != ["PASS_PARTIAL_EXACT_69_CONTINUATION_ERRORS_PRESERVED_CAPTURE_PLAN_BLOCKED"]:
        errors.append("Alternative-acquisition activation statuses changed")

    canary = protocol.get("canary_contract", {})
    parsed_endpoint = urllib.parse.urlsplit(str(canary.get("endpoint", "")))
    if parsed_endpoint.scheme != "https" or parsed_endpoint.hostname != "web.archive.org" or parsed_endpoint.path != "/cdx/search/cdx":
        errors.append("CDX canary endpoint changed")
    expected_canary = {"target_availability_plan_id": "TTCV1_B3_AVAIL_002", "target_must_be_first_never_attempted_continuation_row": True, "metadata_only": True, "maximum_logical_requests": 1, "maximum_attempts": 1, "minimum_delay_seconds": 60.0, "maximum_redirects": 0, "output": "json", "maximum_rows": 1000, "stop_on_http_429": True, "partial_journal_reserved_before_network": True, "partial_journal_auto_resume_allowed": False, "output_overwrite_allowed": False, "archived_page_download_allowed": False}
    for field, value in expected_canary.items():
        if canary.get(field) != value:
            errors.append(f"CDX canary contract changed: {field}")
    if canary.get("fields") != ["timestamp", "original", "statuscode", "mimetype", "digest"] or canary.get("filters") != ["statuscode:200", "mimetype:text/html"] or canary.get("allowed_network_hosts") != ["web.archive.org"]:
        errors.append("CDX canary fields/filters/allowlist changed")

    branches = protocol.get("branch_contract", {})
    required_branches = {"canary_http_200_valid_json", "canary_http_429", "canary_http_4xx_non_429", "canary_invalid_content_or_parser_limitation", "canary_empty_result"}
    if not required_branches.issubset(branches) or branches.get("maximum_identical_canary_attempts") != 1 or branches.get("automatic_fallback_cascade_allowed") is not False:
        errors.append("Alternative-acquisition finite branch contract changed")
    decision = protocol.get("decision", {})
    if decision.get("fallback_preparation_complete") is not True or decision.get("fallback_network_execution_allowed_now") is not False or decision.get("continuation_bypassed") is not False or decision.get("quarantined_row_retry_allowed") is not False:
        errors.append("Alternative-acquisition decision opened a forbidden network path")
    for gate in ("candidate_live_domain_access_allowed", "archived_page_download_allowed", "artifact_capture_allowed", "availability_or_cdx_membership_as_label_allowed", "validation_or_test_opening_allowed", "model_scoring_allowed", "training_allowed"):
        if decision.get(gate) is not False:
            errors.append(f"Alternative-acquisition forbidden gate opened: {gate}")
    return {"verification_id": QA_ID, "status": PASS_STATUS if not errors else "FAIL", "protocol": {"path": str(protocol_path.resolve()), "sha256": sha256_file(protocol_path)}, "checks": {"continuation_rows": len(remaining), "canary_rows": population.get("canary_rows"), "canary_id": canary.get("target_availability_plan_id"), "maximum_canary_requests": canary.get("maximum_logical_requests"), "metadata_only": canary.get("metadata_only"), "activation_is_conditional": activation.get("continuation_final_report_required"), "network_operations": 0}, "decision": {"protocol_prepared": not errors, "network_execution_allowed_now": False, "continuation_must_execute_first": True, "training_allowed": False}, "errors": errors, "safety_contract": {"network_operations": 0, "candidate_domain_access_operations": 0, "archived_page_downloads": 0, "captures": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.protocol)
    if args.output and result["status"] != "FAIL":
        partial = args.output.with_suffix(args.output.suffix + ".partial")
        if args.output.exists() or partial.exists():
            raise FileExistsError("Refusing to overwrite alternative-acquisition protocol QA")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
