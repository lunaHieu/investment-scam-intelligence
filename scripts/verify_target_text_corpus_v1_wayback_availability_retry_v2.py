"""Verify the unresolved-only Wayback availability retry V2 plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.retry_target_text_corpus_v1_wayback_availability import validate_protocol


ANALYSIS_ID = "ISI_TARGET_TEXT_CORPUS_V1_WAYBACK_AVAILABILITY_RETRY_V2"
EXPECTED_STATUS = "FROZEN_UNRESOLVED_ONLY_RETRY_READY_NOT_EXECUTED"
EXPECTED_SAFETY = {
    "network_operations": 0,
    "historical_availability_network_operations_registered": 10,
    "domain_access_allowed": False,
    "candidate_domain_access_operations": 0,
    "archived_page_download_operations": 0,
    "candidate_artifact_captures": 0,
    "labels_created": 0,
    "labels_changed": 0,
    "model_fit_operations": 0,
    "model_scoring_operations": 0,
    "validation_or_test_openings": 0,
    "training_allowed": False,
    "deployment_allowed": False,
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
    for item in (
        list(registry.get("inputs", []))
        + list(registry.get("implementation", []))
        + list(registry.get("outputs", []))
    ):
        role = str(item.get("role"))
        path = resolve(root, item.get("path", ""))
        actual = sha256_file(path) if path.is_file() else None
        role_paths[role] = path
        checked.append({"role": role, "path": str(path), "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"Artifact missing or changed: {role}")
    required = {
        "availability_plan_registry_v1",
        "partial_availability_report_v1",
        "availability_retry_protocol_v2",
        "availability_retry_runner_v2",
        "availability_retry_tests_v2",
        "availability_retry_verifier_v2",
        "availability_retry_verifier_tests_v2",
        "method_documentation",
    }
    missing = sorted(required - role_paths.keys())
    if missing:
        errors.append(f"Registry lacks required roles: {missing}")
    protocol_path = role_paths.get("availability_retry_protocol_v2")
    validation: dict[str, Any] = {}
    if protocol_path is not None and protocol_path.is_file():
        validation = validate_protocol(protocol_path)
        errors.extend(validation["errors"])
    runner_path = role_paths.get("availability_retry_runner_v2")
    if runner_path is not None and runner_path.is_file():
        source = runner_path.read_text(encoding="utf-8")
        for guard in (
            'if prior_row.get("error") is None:',
            'output_path.open("x"',
            "except RateLimitStop",
            '"candidate_live_domain_access_operations": 0',
            '"archived_page_download_operations": 0',
        ):
            if guard not in source:
                errors.append(f"Retry safety guard missing: {guard}")
    if registry.get("safety_contract") != EXPECTED_SAFETY:
        errors.append("Registry safety contract changed")
    decision = registry.get("decision", {})
    if decision.get("unresolved_only_retry_allowed") is not True:
        errors.append("Unresolved-only retry was not released")
    if decision.get("candidate_capture_allowed") is not False:
        errors.append("Candidate capture must remain blocked")
    if registry.get("outputs") != []:
        errors.append("Retry plan must not pre-register an output")
    return {
        "analysis_id": registry.get("analysis_id"),
        "valid": not errors,
        "status": registry.get("status"),
        "checked_artifact_count": len(checked),
        "retry_candidate_count": validation.get("retry_candidate_count"),
        "unresolved_only_retry_allowed": True,
        "candidate_capture_allowed": False,
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
