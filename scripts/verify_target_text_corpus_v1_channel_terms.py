"""Verify source registration and capture-channel terms for Target Text Corpus V1."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_ID = "ISI_TARGET_TEXT_CORPUS_V1_CHANNEL_TERMS_V1"
EXPECTED_STATUS = "FROZEN_CHANNEL_TERMS_REVIEW_COMPLETE_ACQUISITION_BLOCKED"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def resolve(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def validate_protocol(protocol_path: Path) -> dict[str, Any]:
    protocol = load_json(protocol_path)
    root = protocol_path.resolve().parents[1]
    errors: list[str] = []
    for item in protocol.get("basis", []):
        path = resolve(root, item.get("path", ""))
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            errors.append(f"Basis artifact missing or changed: {item.get('role')}")

    source_item = next(
        (item for item in protocol.get("basis", []) if item.get("role") == "source_addendum"),
        None,
    )
    addendum: dict[str, Any] = {}
    if source_item is None:
        errors.append("Source addendum basis missing")
    else:
        addendum = load_json(resolve(root, source_item["path"]))
        if addendum.get("status") != "FROZEN_SOURCE_REGISTRATION_ADDENDUM_NO_ACQUISITION":
            errors.append("Source addendum status changed")
        sources = {item.get("source_id"): item for item in addendum.get("sources", [])}
        if set(sources) != {"cftc_red_list", "sec_edgar_company_submissions"}:
            errors.append("Source addendum membership changed")
        for source_id, source in sources.items():
            for field in ("url",):
                if urlparse(str(source.get(field, ""))).scheme != "https":
                    errors.append(f"Non-HTTPS source URL: {source_id}")
            terms_url = source.get("terms_review", {}).get("official_policy_url", "")
            if urlparse(str(terms_url)).scheme != "https":
                errors.append(f"Non-HTTPS terms URL: {source_id}")
            if source.get("case_level_target_eligible_without_additional_review") is not False:
                errors.append(f"Source improperly authorizes target labels: {source_id}")
        if sources.get("cftc_red_list", {}).get("default_evidence_level") != "SILVER":
            errors.append("CFTC evidence level changed")
        if (
            sources.get("sec_edgar_company_submissions", {}).get("default_evidence_level")
            != "LEGIT_REFERENCE"
        ):
            errors.append("SEC EDGAR evidence level changed")

    amendments = protocol.get("channel_amendments", [])
    if {item.get("channel_id") for item in amendments} != {
        "CONFIRMED_CFTC_RED_LINKED_WAYBACK_WEBSITE",
        "LEGITIMATE_SEC_EDGAR_LINKED_WAYBACK_WEBSITE",
    }:
        errors.append("Replacement channel set changed")
    if any(item.get("predicted_artifact_type") != "WEBSITE_SNAPSHOT" for item in amendments):
        errors.append("Replacement artifact modality changed")
    if {item.get("planned_target_status") for item in amendments} != {
        "CONFIRMED",
        "LEGITIMATE",
    }:
        errors.append("Replacement target-status coverage changed")

    balance = protocol.get("balance_after_amendment", {})
    if balance.get("protocol_registered_channels_by_target_status") != {
        "CONFIRMED": 2,
        "LEGITIMATE": 2,
    }:
        errors.append("Channel balance changed")
    if balance.get("channel_protocol_registration_gate_passed") is not True:
        errors.append("Channel protocol registration gate did not pass")
    for gate in (
        "candidate_enumeration_gate_passed",
        "candidate_capture_gate_passed",
        "binary_labeling_gate_passed",
    ):
        if balance.get(gate) is not False:
            errors.append(f"Gate unexpectedly opened: {gate}")

    capture = protocol.get("shared_wayback_capture_contract", {})
    if capture.get("allowed_network_hosts") != ["archive.org", "web.archive.org"]:
        errors.append("Wayback host allowlist changed")
    if capture.get("candidate_live_domain_access_allowed") is not False:
        errors.append("Live candidate-domain access opened")
    if capture.get("request_rate_per_second_maximum") != 1:
        errors.append("Wayback request cap changed")

    reference = protocol.get("reference_access_contract", {})
    if reference.get("cftc", {}).get("automated_scraping_authorized") is not False:
        errors.append("CFTC generic scraping unexpectedly authorized")
    sec = reference.get("sec", {})
    if (
        sec.get("maximum_requests_per_second") != 1
        or sec.get("official_policy_maximum_requests_per_second") != 10
        or sec.get("truthful_user_agent_contact_identity_required") is not True
        or sec.get("contact_identity_configured") is not False
        or sec.get("network_execution_allowed") is not False
    ):
        errors.append("SEC fair-access execution contract changed")

    expected_safety = {
        "network_operations_after_protocol_freeze": 0,
        "domain_access_allowed": False,
        "candidate_records_enumerated": 0,
        "new_records_acquired": 0,
        "new_artifact_captures": 0,
        "labels_created": 0,
        "labels_changed": 0,
        "model_fit_operations": 0,
        "model_scoring_operations": 0,
        "validation_or_test_openings": 0,
        "training_allowed": False,
        "deployment_allowed": False,
    }
    if protocol.get("safety_contract") != expected_safety:
        errors.append("Protocol safety contract changed")

    return {
        "valid": not errors,
        "protocol_id": protocol.get("protocol_id"),
        "source_count": len(addendum.get("sources", [])),
        "replacement_channel_count": len(amendments),
        "registered_channels_by_target_status": balance.get(
            "protocol_registered_channels_by_target_status"
        ),
        "channel_protocol_registration_gate_passed": balance.get(
            "channel_protocol_registration_gate_passed"
        ),
        "candidate_enumeration_allowed": False,
        "candidate_capture_allowed": False,
        "model_fit_operations": 0,
        "errors": errors,
    }


def verify_registry(registry_path: Path) -> dict[str, Any]:
    registry = load_json(registry_path)
    root = registry_path.resolve().parents[2]
    errors: list[str] = []
    role_paths: dict[str, Path] = {}
    checked: list[dict[str, object]] = []
    if registry.get("analysis_id") != ANALYSIS_ID:
        errors.append("Unexpected analysis ID")
    if registry.get("status") != EXPECTED_STATUS:
        errors.append("Unexpected registry status")
    for item in (
        list(registry.get("inputs", []))
        + list(registry.get("implementation", []))
        + list(registry.get("outputs", []))
    ):
        role = str(item.get("role"))
        path = resolve(root, item.get("path", ""))
        actual_hash = sha256_file(path) if path.is_file() else None
        if role in role_paths:
            errors.append(f"Duplicate artifact role: {role}")
        role_paths[role] = path
        checked.append({"role": role, "path": str(path), "sha256": actual_hash})
        if actual_hash != item.get("sha256"):
            errors.append(f"Artifact missing or changed: {role}")

    protocol_path = role_paths.get("channel_terms_protocol")
    protocol_result: dict[str, Any] = {}
    if protocol_path is None:
        errors.append("Channel terms protocol missing")
    else:
        protocol_result = validate_protocol(protocol_path)
        errors.extend(protocol_result["errors"])

    expected_registry_safety = {
        "network_operations": 0,
        "domain_access_allowed": False,
        "candidate_records_enumerated": 0,
        "new_records_acquired": 0,
        "new_artifact_captures": 0,
        "labels_created": 0,
        "labels_changed": 0,
        "model_fit_operations": 0,
        "model_scoring_operations": 0,
        "validation_or_test_openings": 0,
        "training_allowed": False,
        "deployment_allowed": False,
    }
    if registry.get("safety_contract") != expected_registry_safety:
        errors.append("Registry safety contract changed")

    return {
        "analysis_id": registry.get("analysis_id"),
        "valid": not errors,
        "status": registry.get("status"),
        "checked_artifact_count": len(checked),
        "source_count": protocol_result.get("source_count"),
        "replacement_channel_count": protocol_result.get("replacement_channel_count"),
        "channel_protocol_registration_gate_passed": protocol_result.get(
            "channel_protocol_registration_gate_passed"
        ),
        "candidate_capture_allowed": False,
        "model_fit_operations": 0,
        "errors": errors,
        "checked": checked,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--registry", type=Path)
    args = parser.parse_args()
    if (args.protocol is None) == (args.registry is None):
        parser.error("provide exactly one of --protocol or --registry")
    result = (
        validate_protocol(args.protocol)
        if args.protocol is not None
        else verify_registry(args.registry)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
