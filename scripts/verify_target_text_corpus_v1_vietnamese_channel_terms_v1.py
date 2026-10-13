"""Verify Vietnamese reference-source roles and closed acquisition gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def verify(protocol_path: Path) -> dict[str, Any]:
    protocol = load_object(protocol_path)
    errors: list[str] = []
    if protocol.get("protocol_id") != "ISI_TARGET_TEXT_CORPUS_V1_VIETNAMESE_CHANNEL_TERMS_V1":
        errors.append("Unexpected Vietnamese channel terms protocol")
    root = protocol_path.resolve().parents[1]
    for item in protocol.get("basis", []):
        if sha256_file(root / item["path"]) != item["sha256"]:
            errors.append(f"Basis mismatch: {item['role']}")
    addendum_item = next((item for item in protocol["basis"] if item["role"] == "vietnamese_source_addendum"), None)
    if addendum_item is None:
        errors.append("Vietnamese source addendum missing")
        addendum = {}
    else:
        addendum = load_object(root / addendum_item["path"])
    sources = {item.get("source_id"): item for item in addendum.get("sources", [])}
    if set(sources) != {"ssc_vietnam_investor_warnings", "hnx_vietnam_issuer_profiles"}:
        errors.append("Vietnamese source membership changed")
    for source_id, source in sources.items():
        if urlparse(str(source.get("official_url", ""))).scheme != "https":
            errors.append(f"Non-HTTPS source URL: {source_id}")
        if source.get("case_level_target_eligible_without_additional_review") is not False:
            errors.append(f"Source improperly creates labels: {source_id}")
        terms = source.get("terms_and_access_review", {})
        if terms.get("acquisition_ready") is not False or not terms.get("blocker"):
            errors.append(f"Source acquisition gate unexpectedly open: {source_id}")
    paths = protocol.get("channel_paths", [])
    if {item.get("target_status") for item in paths} != {"CONFIRMED", "LEGITIMATE"}:
        errors.append("Vietnamese channel target-status coverage changed")
    if {item.get("reference_source_id") for item in paths} != set(sources):
        errors.append("Protocol/addendum source mismatch")
    if any(item.get("activation_status") != "SOURCE_ROLE_REGISTERED_ACQUISITION_BLOCKED" for item in paths):
        errors.append("Vietnamese channel activation state changed")
    rights = protocol.get("rights_and_access_contract", {})
    for key in ("generic_automated_scraping_authorized", "manual_record_level_review_allowed_after_release", "full_source_page_or_data_bundle_redistribution_allowed", "minimal_derived_provenance_external_release_allowed_now", "official_reference_text_as_model_input", "candidate_live_domain_access_allowed", "legal_opinion_claimed"):
        if rights.get(key) is not False:
            errors.append(f"Rights/access prohibition changed: {key}")
    matrix = protocol.get("matrix_contract", {})
    if matrix.get("sampling_matrix_v2_required_before_adoption") is not True or matrix.get("sampling_matrix_v1_silently_modified") is not False:
        errors.append("Sampling matrix amendment contract changed")
    for key in ("class_quota_change_allowed_by_this_protocol", "channel_fraction_cap_change_allowed_by_this_protocol", "language_quota_waiver_allowed", "language_supply_claim_allowed_before_artifact_review"):
        if matrix.get(key) is not False:
            errors.append(f"Matrix prohibition changed: {key}")
    decision = protocol.get("decision", {})
    if decision.get("source_role_registration_gate_passed") is not True or decision.get("terms_review_recorded") is not True:
        errors.append("Source-role registration did not pass")
    for key in ("reference_acquisition_gate_passed", "sampling_matrix_amendment_gate_passed", "candidate_enumeration_allowed", "artifact_capture_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "training_allowed"):
        if decision.get(key) is not False:
            errors.append(f"Forbidden decision gate opened: {key}")
    expected_safety = {"candidate_domain_access_operations": 0, "reference_records_acquired": 0, "candidate_records_enumerated": 0, "artifact_captures": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False}
    if protocol.get("safety_contract") != expected_safety or addendum.get("safety_contract") != expected_safety:
        errors.append("Vietnamese source safety contract changed")
    return {
        "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_VIETNAMESE_CHANNEL_TERMS_INDEPENDENT_QA_V1",
        "status": "PASS_SOURCE_ROLES_REGISTERED_ACQUISITION_AND_MATRIX_BLOCKED" if not errors else "FAIL",
        "inputs": {"protocol_sha256": sha256_file(protocol_path), "source_addendum_sha256": sha256_file(root / addendum_item["path"]) if addendum_item else None},
        "checks": {"source_count": len(sources), "target_status_count": len({item.get('target_status') for item in paths}), "source_role_registration_gate_passed": not errors, "reference_acquisition_gate_passed": False, "sampling_matrix_v2_required": True},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "candidate_domain_access_operations": 0, "reference_records_acquired": 0, "captures": 0, "labels": 0, "model": 0}
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.protocol)
    if args.output:
        if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
            raise FileExistsError("Refusing to overwrite Vietnamese terms QA")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".partial")
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
