"""Verify the frozen Target Text Corpus V1 Wayback capture-result registry V2."""

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

from scripts.verify_target_text_corpus_v1_wayback_capture_result_v2 import verify


ANALYSIS_ID = "ISI_TARGET_TEXT_CORPUS_V1_WAYBACK_CAPTURE_RESULT_V2"
EXPECTED_STATUS = "FROZEN_23_RAW_CAPTURES_QA_PASS_6_FAILURES_PRESERVED"
EXPECTED_SAFETY = {
    "network_operations": 0,
    "historical_capture_network_operations_registered": 30,
    "domain_access_allowed": False,
    "candidate_domain_access_operations": 0,
    "new_artifact_captures": 0,
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
        "capture_retry_registry_v2", "frozen_capture_plan_v1",
        "capture_report_v1", "capture_report_v2", "independent_capture_qa_v2",
        "capture_result_verifier_v2", "capture_result_verifier_tests_v2",
        "capture_result_registry_verifier_v2",
        "capture_result_registry_verifier_tests_v2", "method_documentation",
    }
    missing = sorted(required - role_paths.keys())
    if missing:
        errors.append(f"Registry lacks required roles: {missing}")
    if not missing:
        result = verify(
            plan_path=role_paths["frozen_capture_plan_v1"],
            v1_path=role_paths["capture_report_v1"],
            v2_path=role_paths["capture_report_v2"],
        )
        errors.extend(result["errors"])
        qa = load_json(role_paths["independent_capture_qa_v2"])
        if qa.get("status") != "PASS_23_RAW_CAPTURES_6_SMALL_RESPONSES_PRESERVED":
            errors.append("Independent raw-capture QA status changed")
    if registry.get("safety_contract") != EXPECTED_SAFETY:
        errors.append("Registry safety contract changed")
    decision = registry.get("decision", {})
    if decision.get("exact_text_extraction_allowed_for_captured_rows") is not True:
        errors.append("Exact-text extraction was not released")
    if decision.get("binary_labeling_allowed") is not False:
        errors.append("Binary labeling must remain blocked")
    return {
        "analysis_id": registry.get("analysis_id"),
        "valid": not errors,
        "status": registry.get("status"),
        "checked_artifact_count": len(checked),
        "captured_count": 23,
        "failed_count": 6,
        "exact_text_extraction_allowed_for_captured_rows": True,
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
