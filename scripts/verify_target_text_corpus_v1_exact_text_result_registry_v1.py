"""Verify the registered Target Text Corpus V1 exact-text result V1."""

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

from scripts.verify_target_text_corpus_v1_exact_text import verify


ANALYSIS_ID = "ISI_TARGET_TEXT_CORPUS_V1_EXACT_TEXT_RESULT_V1"
EXPECTED_STATUS = "FROZEN_EXACT_TEXT_QA_PASS_22_REVIEWABLE_1_BELOW_MINIMUM"
EXPECTED_SAFETY = {
    "network_operations": 0,
    "domain_access_allowed": False,
    "raw_files_modified": False,
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
        "extraction_config", "capture_result_registry_v2", "extractor",
        "independent_verifier", "extraction_tests", "method_documentation",
        "result_documentation", "exact_text_manifest", "extraction_report",
        "independent_exact_text_qa", "registry_verifier", "registry_verifier_tests",
    }
    missing = sorted(required - role_paths.keys())
    if missing:
        errors.append(f"Registry lacks required roles: {missing}")
    if not missing:
        audit = verify(role_paths["extraction_config"])
        errors.extend(audit.get("errors", []))
        frozen_qa = load_json(role_paths["independent_exact_text_qa"])
        if audit.get("status") != "PASS_EXACT_TEXT_BYTES_REGENERATED":
            errors.append("Live independent exact-text audit failed")
        if frozen_qa.get("status") != "PASS_EXACT_TEXT_BYTES_REGENERATED":
            errors.append("Frozen independent exact-text QA status changed")
        if frozen_qa.get("checks", {}).get("byte_for_byte_match_count") != 23:
            errors.append("Frozen byte-for-byte match count changed")
    if registry.get("safety_contract") != EXPECTED_SAFETY:
        errors.append("Registry safety contract changed")
    findings = registry.get("findings", {})
    if findings.get("extracted_count") != 23:
        errors.append("Registered extraction count changed")
    if findings.get("minimum_content_passed_count") != 22:
        errors.append("Registered minimum-content pass count changed")
    if findings.get("below_minimum_candidate_ids") != ["TTCV1_CAND_CONF_CFTC_008"]:
        errors.append("Registered below-minimum candidate changed")
    decision = registry.get("decision", {})
    if decision.get("post_capture_exclusion_and_grouping_allowed") is not True:
        errors.append("Post-capture exclusion/grouping was not released")
    if decision.get("human_label_review_allowed") is not False:
        errors.append("Human label review must remain blocked")
    return {
        "analysis_id": registry.get("analysis_id"),
        "valid": not errors,
        "status": registry.get("status"),
        "checked_artifact_count": len(checked),
        "extracted_count": 23,
        "minimum_content_passed_count": 22,
        "below_minimum_preserved_count": 1,
        "post_capture_exclusion_and_grouping_allowed": True,
        "human_label_review_allowed": False,
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
