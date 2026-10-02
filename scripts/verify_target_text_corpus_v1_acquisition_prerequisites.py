"""Verify the privacy-preserving acquisition-prerequisite intake gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_ID = "ISI_TARGET_TEXT_CORPUS_V1_ACQUISITION_PREREQUISITE_INTAKE_V1"
EXPECTED_STATUS = "FROZEN_PREREQUISITE_INTAKE_READY_EXTERNAL_INPUTS_MISSING"
EXPECTED_SAFETY = {
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
EXPECTED_PREREQUISITES = {
    "CFTC_RED_REFERENCE_ARTIFACT": "CONFIRMED_CFTC_RED_LINKED_WAYBACK_WEBSITE",
    "SEC_EDGAR_USER_AGENT_IDENTITY": "LEGITIMATE_SEC_EDGAR_LINKED_WAYBACK_WEBSITE",
}


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


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def validate_ledger(ledger: dict[str, Any], *, require_blocked: bool = True) -> list[str]:
    errors: list[str] = []
    if ledger.get("ledger_id") != "ISI_TARGET_TEXT_CORPUS_V1_ACQUISITION_PREREQUISITES":
        errors.append("Unexpected ledger ID")
    if ledger.get("ledger_version") != 1:
        errors.append("Unexpected ledger version")
    if ledger.get("public_repo_contains_contact_identity") is not False:
        errors.append("Ledger claims contact identity is public")
    prerequisites = ledger.get("prerequisites", [])
    if not isinstance(prerequisites, list):
        errors.append("Prerequisites must be a list")
        prerequisites = []
    by_id = {str(item.get("prerequisite_id")): item for item in prerequisites if isinstance(item, dict)}
    if set(by_id) != set(EXPECTED_PREREQUISITES) or len(prerequisites) != 2:
        errors.append("Prerequisite membership changed")
    for prerequisite_id, channel_id in EXPECTED_PREREQUISITES.items():
        item = by_id.get(prerequisite_id, {})
        if item.get("channel_id") != channel_id:
            errors.append(f"Prerequisite channel mismatch: {prerequisite_id}")
        if not str(item.get("required_action", "")).strip():
            errors.append(f"Required action missing: {prerequisite_id}")
        for field in ("official_source_url", "official_policy_url"):
            parsed = urlparse(str(item.get(field, "")))
            if parsed.scheme != "https" or not parsed.netloc:
                errors.append(f"Official HTTPS URL missing: {prerequisite_id}/{field}")
        disclosure = item.get("public_registry_disclosure", {})
        if disclosure.get("readiness_only") is not True:
            errors.append(f"Readiness-only disclosure changed: {prerequisite_id}")
        if disclosure.get("contact_identity_allowed") is not False:
            errors.append(f"Contact identity disclosure opened: {prerequisite_id}")
        artifact = item.get("local_artifact", {})
        if not str(artifact.get("path", "")).strip():
            errors.append(f"Local artifact path missing: {prerequisite_id}")
        if require_blocked:
            if item.get("readiness") != "MISSING":
                errors.append(f"Frozen missing prerequisite unexpectedly ready: {prerequisite_id}")
            if artifact.get("exists") is not False:
                errors.append(f"Frozen missing artifact unexpectedly exists: {prerequisite_id}")
            if artifact.get("sha256") is not None or artifact.get("recorded_at") is not None:
                errors.append(f"Frozen missing artifact contains readiness evidence: {prerequisite_id}")
    if require_blocked:
        if ledger.get("status") != "BLOCKED_MISSING_EXTERNAL_INPUTS":
            errors.append("Blocked ledger status changed")
        expected_gate = {
            "all_prerequisites_ready": False,
            "candidate_enumeration_allowed": False,
            "network_execution_allowed": False,
        }
        if ledger.get("release_gate") != expected_gate:
            errors.append("Blocked ledger release gate changed")
    serialized = json.dumps(ledger, ensure_ascii=False)
    if re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", serialized, re.IGNORECASE):
        errors.append("Ledger contains an email address")
    return errors


def validate_protocol(protocol_path: Path) -> dict[str, Any]:
    protocol = load_json(protocol_path)
    root = protocol_path.resolve().parents[1]
    errors: list[str] = []
    checked: list[dict[str, object]] = []
    role_paths: dict[str, Path] = {}
    for item in protocol.get("basis", []):
        role = str(item.get("role"))
        path = resolve(root, item.get("path", ""))
        actual = sha256_file(path) if path.is_file() else None
        role_paths[role] = path
        checked.append({"role": role, "path": str(path), "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"Basis artifact missing or changed: {role}")

    template_path = role_paths.get("public_example_ledger")
    ledger_path = role_paths.get("local_prerequisite_ledger")
    template: dict[str, Any] = {}
    ledger: dict[str, Any] = {}
    if template_path is None:
        errors.append("Public example ledger missing")
    else:
        template = load_json(template_path)
        errors.extend(validate_ledger(template))
    if ledger_path is None:
        errors.append("Local prerequisite ledger missing")
    else:
        ledger = load_json(ledger_path)
        errors.extend(validate_ledger(ledger))
    if template and ledger and template != ledger:
        errors.append("Initial local ledger differs from the frozen public example")

    storage = protocol.get("storage_contract", {})
    data_root = Path(str(storage.get("data_root", "")))
    if not data_root.is_absolute():
        errors.append("Data root must be absolute")
    for field in ("cftc_raw_directory", "sec_private_directory", "local_ledger_directory"):
        path = Path(str(storage.get(field, "")))
        if not path.is_dir() or not _is_under(path, data_root):
            errors.append(f"Storage path missing or outside data root: {field}")
    if storage.get("raw_artifact_overwrite_allowed") is not False:
        errors.append("Raw artifact overwrite opened")

    privacy = protocol.get("privacy_contract", {})
    expected_privacy = {
        "repository_is_public": True,
        "contact_identity_allowed_in_repository": False,
        "contact_email_allowed_in_repository_registry": False,
        "private_identity_file_path_allowed_in_repository": True,
        "private_identity_file_contents_allowed_in_repository": False,
        "private_identity_file_sha256_allowed_in_repository": False,
        "future_public_readiness_disclosure": "BOOLEAN_ONLY",
        "truthful_identity_required_before_sec_network_access": True,
    }
    if privacy != expected_privacy:
        errors.append("Privacy contract changed")
    private_path = Path(str(protocol.get("private_sec_file_contract", {}).get("path", "")))
    if not private_path.is_absolute() or not _is_under(private_path, data_root):
        errors.append("Private SEC file path is not contained by the data root")
    if _is_under(private_path, root):
        errors.append("Private SEC file path is inside the public repository")
    if private_path.exists():
        errors.append("Private SEC identity unexpectedly exists in frozen missing-input state")

    cftc = protocol.get("cftc_artifact_contract", {})
    if cftc.get("generic_scraping_authorized") is not False:
        errors.append("Generic CFTC scraping opened")
    if cftc.get("allowed_acquisition_modes") != ["MANUAL_DOWNLOAD", "EXPLICIT_OFFICIAL_DOWNLOAD"]:
        errors.append("CFTC acquisition modes changed")
    sec = protocol.get("sec_access_contract", {})
    if sec.get("project_request_rate_per_second_maximum") != 1:
        errors.append("SEC project request cap changed")
    if sec.get("contact_identity_currently_configured") is not False:
        errors.append("SEC identity incorrectly marked configured")
    if sec.get("network_execution_allowed") is not False:
        errors.append("SEC network execution opened")

    blockers = protocol.get("current_blockers", [])
    blocker_map = {item.get("prerequisite_id"): item for item in blockers}
    if set(blocker_map) != set(EXPECTED_PREREQUISITES):
        errors.append("Current blocker set changed")
    if any(item.get("status") != "MISSING" for item in blockers):
        errors.append("Frozen blocker unexpectedly cleared")
    release = protocol.get("release_rule", {})
    if release.get("all_prerequisites_must_be_ready") is not True:
        errors.append("All-prerequisite release rule changed")
    if release.get("independent_intake_verification_required") is not True:
        errors.append("Independent intake verification requirement changed")
    if release.get("candidate_enumeration_allowed") is not False:
        errors.append("Candidate enumeration opened")
    if release.get("network_execution_allowed") is not False:
        errors.append("Network execution opened")
    if protocol.get("safety_contract") != EXPECTED_SAFETY:
        errors.append("Protocol safety contract changed")

    return {
        "valid": not errors,
        "protocol_id": protocol.get("protocol_id"),
        "status": protocol.get("status"),
        "checked_artifact_count": len(checked),
        "prerequisite_count": len(ledger.get("prerequisites", [])),
        "ready_prerequisite_count": sum(
            item.get("readiness") == "READY" for item in ledger.get("prerequisites", [])
        ),
        "missing_prerequisite_count": sum(
            item.get("readiness") == "MISSING" for item in ledger.get("prerequisites", [])
        ),
        "contact_identity_exposed": False,
        "candidate_enumeration_allowed": False,
        "network_execution_allowed": False,
        "errors": errors,
        "checked": checked,
    }


def verify_registry(registry_path: Path) -> dict[str, Any]:
    registry = load_json(registry_path)
    root = registry_path.resolve().parents[2]
    errors: list[str] = []
    checked: list[dict[str, object]] = []
    role_paths: dict[str, Path] = {}
    if registry.get("analysis_id") != ANALYSIS_ID:
        errors.append("Unexpected analysis ID")
    if registry.get("status") != EXPECTED_STATUS:
        errors.append("Unexpected registry status")
    items = (
        list(registry.get("inputs", []))
        + list(registry.get("implementation", []))
        + list(registry.get("outputs", []))
    )
    for item in items:
        role = str(item.get("role"))
        path = resolve(root, item.get("path", ""))
        actual = sha256_file(path) if path.is_file() else None
        if role in role_paths:
            errors.append(f"Duplicate artifact role: {role}")
        role_paths[role] = path
        checked.append({"role": role, "path": str(path), "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"Artifact missing or changed: {role}")
    protocol_path = role_paths.get("acquisition_prerequisite_intake_protocol")
    protocol_result: dict[str, Any] = {}
    if protocol_path is None:
        errors.append("Acquisition-prerequisite intake protocol missing")
    else:
        protocol_result = validate_protocol(protocol_path)
        errors.extend(protocol_result["errors"])
    if registry.get("safety_contract") != EXPECTED_SAFETY:
        errors.append("Registry safety contract changed")
    return {
        "analysis_id": registry.get("analysis_id"),
        "valid": not errors,
        "status": registry.get("status"),
        "checked_artifact_count": len(checked),
        "ready_prerequisite_count": protocol_result.get("ready_prerequisite_count"),
        "missing_prerequisite_count": protocol_result.get("missing_prerequisite_count"),
        "contact_identity_exposed": False,
        "candidate_enumeration_allowed": False,
        "network_execution_allowed": False,
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
