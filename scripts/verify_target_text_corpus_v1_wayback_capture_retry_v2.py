"""Verify the cooldown-gated Target Text Corpus V1 capture retry plan."""

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

from scripts.retry_target_text_corpus_v1_wayback_capture import validate_protocol


ANALYSIS_ID = "ISI_TARGET_TEXT_CORPUS_V1_WAYBACK_CAPTURE_RETRY_V2"
EXPECTED_STATUS = "FROZEN_COOLDOWN_RETRY_QA_PASS_EXECUTION_AUTHORIZED"
EXPECTED_SAFETY = {
    "network_operations": 0,
    "historical_capture_network_operations_registered": 1,
    "domain_access_allowed": False,
    "candidate_domain_access_operations": 0,
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
        "capture_plan_registry_v1",
        "failed_capture_report_v1",
        "capture_retry_protocol_v2",
        "capture_retry_runner_v2",
        "capture_retry_tests_v2",
        "capture_retry_verifier_v2",
        "capture_retry_verifier_tests_v2",
        "method_documentation",
    }
    missing = sorted(required - role_paths.keys())
    if missing:
        errors.append(f"Registry lacks required roles: {missing}")
    validation: dict[str, Any] = {}
    protocol_path = role_paths.get("capture_retry_protocol_v2")
    if protocol_path is not None and protocol_path.is_file():
        validation = validate_protocol(protocol_path)
        errors.extend(validation["errors"])
    runner_path = role_paths.get("capture_retry_runner_v2")
    if runner_path is not None and runner_path.is_file():
        source = runner_path.read_text(encoding="utf-8")
        for guard in (
            'if prior_row.get("outcome") == "CAPTURED":',
            'with target.open("xb")',
            "if error.code == 429:",
            '"candidate_live_domain_access_operations": 0',
            'float(retry["minimum_delay_seconds"])',
        ):
            if guard not in source:
                errors.append(f"Capture retry safety guard missing: {guard}")
    if registry.get("safety_contract") != EXPECTED_SAFETY:
        errors.append("Registry safety contract changed")
    decision = registry.get("decision", {})
    if decision.get("capture_retry_allowed") is not True:
        errors.append("Capture retry was not released")
    if decision.get("text_extraction_allowed") is not False:
        errors.append("Text extraction must remain blocked")
    if decision.get("binary_labeling_allowed") is not False:
        errors.append("Binary labeling must remain blocked")
    if registry.get("outputs") != []:
        errors.append("Retry gate must not pre-register an execution output")
    return {
        "analysis_id": registry.get("analysis_id"),
        "valid": not errors,
        "status": registry.get("status"),
        "checked_artifact_count": len(checked),
        "retry_candidate_count": validation.get("retry_candidate_count"),
        "cooldown_ready": validation.get("cooldown_ready"),
        "capture_retry_allowed": True,
        "text_extraction_allowed": False,
        "binary_labeling_allowed": False,
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
