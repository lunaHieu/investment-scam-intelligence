"""Verify offline candidate-enumeration tooling without running production enumeration."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_ID = "ISI_TARGET_TEXT_CORPUS_V1_CANDIDATE_ENUMERATION_TOOLING_V1"
EXPECTED_STATUS = "FROZEN_OFFLINE_ENUMERATION_TOOLING_READY_PRODUCTION_RUN_BLOCKED"
EXPECTED_CHANNELS = {
    "CONFIRMED_REGULATOR_LINKED_WEBSITE",
    "CONFIRMED_CFTC_RED_LINKED_WAYBACK_WEBSITE",
    "LEGITIMATE_REGISTER_LINKED_WEBSITE",
    "LEGITIMATE_SEC_EDGAR_LINKED_WAYBACK_WEBSITE",
}
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
BANNED_NETWORK_IMPORTS = {"requests", "httpx", "aiohttp", "socket", "urllib.request"}


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


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def validate_tooling(
    module_path: Path,
    cli_path: Path,
    protocol_path: Path,
    prerequisite_ledger_path: Path,
) -> dict[str, Any]:
    errors: list[str] = []
    for path in (module_path, cli_path, protocol_path, prerequisite_ledger_path):
        if not path.is_file():
            errors.append(f"Required tooling artifact missing: {path}")
    if errors:
        return {"valid": False, "errors": errors}
    protocol = load_json(protocol_path)
    ledger = load_json(prerequisite_ledger_path)
    quotas = protocol.get("initial_enumeration_wave", {}).get("quota_by_channel", {})
    if set(quotas) != EXPECTED_CHANNELS or set(quotas.values()) != {10}:
        errors.append("Frozen four-channel quota contract changed")
    if protocol.get("initial_enumeration_wave", {}).get("candidate_record_target") != 40:
        errors.append("Frozen initial candidate target changed")
    if ledger.get("status") != "BLOCKED_MISSING_EXTERNAL_INPUTS":
        errors.append("Current prerequisite ledger unexpectedly ready")
    if ledger.get("release_gate") != {
        "all_prerequisites_ready": False,
        "candidate_enumeration_allowed": False,
        "network_execution_allowed": False,
    }:
        errors.append("Current prerequisite ledger gate changed")
    all_imports = imported_modules(module_path) | imported_modules(cli_path)
    banned = sorted(
        imported
        for imported in all_imports
        if imported in BANNED_NETWORK_IMPORTS
        or any(imported.startswith(f"{name}.") for name in BANNED_NETWORK_IMPORTS)
    )
    if banned:
        errors.append(f"Enumeration tooling imports network clients: {banned}")
    module_source = module_path.read_text(encoding="utf-8")
    cli_source = cli_path.read_text(encoding="utf-8")
    for required in (
        "balanced enumeration shortfall; no queue emitted",
        "cross_channel_host_overlap",
        "cross_stratum_entity_overlap",
        '"ground_truth_status": "UNCERTAIN"',
        '"label_created": False',
        '"training_allowed": False',
    ):
        if required not in module_source:
            errors.append(f"Enumeration fail-closed guard missing: {required}")
    for required in (
        "validate_ready_ledger",
        "Refusing to overwrite frozen outputs",
        "Generated candidates failed schema invariants",
        "sha256_file(cftc_path)",
        "SEC private identity must remain outside the public repository",
    ):
        if required not in cli_source:
            errors.append(f"CLI prerequisite/output guard missing: {required}")
    return {
        "valid": not errors,
        "initial_candidate_target": protocol.get("initial_enumeration_wave", {}).get(
            "candidate_record_target"
        ),
        "channel_count": len(quotas),
        "current_prerequisite_status": ledger.get("status"),
        "production_enumeration_allowed": False,
        "network_import_count": len(banned),
        "errors": errors,
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
    required_roles = {
        "schema_review_pilot_protocol",
        "current_prerequisite_ledger",
        "candidate_enumeration_module",
        "candidate_enumeration_cli",
    }
    if not required_roles.issubset(role_paths):
        errors.append("Registry lacks required tooling roles")
        tooling: dict[str, Any] = {}
    else:
        tooling = validate_tooling(
            role_paths["candidate_enumeration_module"],
            role_paths["candidate_enumeration_cli"],
            role_paths["schema_review_pilot_protocol"],
            role_paths["current_prerequisite_ledger"],
        )
        errors.extend(tooling["errors"])
    if registry.get("safety_contract") != EXPECTED_SAFETY:
        errors.append("Registry safety contract changed")
    return {
        "analysis_id": registry.get("analysis_id"),
        "valid": not errors,
        "status": registry.get("status"),
        "checked_artifact_count": len(checked),
        "initial_candidate_target": tooling.get("initial_candidate_target"),
        "channel_count": tooling.get("channel_count"),
        "current_prerequisite_status": tooling.get("current_prerequisite_status"),
        "production_enumeration_allowed": False,
        "network_import_count": tooling.get("network_import_count"),
        "errors": errors,
        "checked": checked,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    args = parser.parse_args()
    result = verify_registry(args.registry)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
