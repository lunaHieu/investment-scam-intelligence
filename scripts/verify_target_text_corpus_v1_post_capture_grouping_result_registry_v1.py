"""Verify the registered Target Text Corpus V1 post-capture grouping result."""

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

from scripts.verify_target_text_corpus_v1_post_capture_grouping import audit


ANALYSIS_ID = "ISI_TARGET_TEXT_CORPUS_V1_POST_CAPTURE_GROUPING_RESULT_V1"
STATUS = "FROZEN_AUTOMATED_GATE_PASS_22_PROVISIONAL_GROUPS_MANUAL_REVIEW_REQUIRED"
SAFETY = {
    "network_operations": 0,
    "domain_access_allowed": False,
    "labels_created": 0,
    "labels_changed": 0,
    "model_fit_operations": 0,
    "model_scoring_operations": 0,
    "validation_or_test_openings": 0,
    "training_allowed": False,
    "deployment_allowed": False,
}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object: {path}")
    return value


def resolve(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def verify_registry(path: Path) -> dict[str, Any]:
    registry = load(path)
    root = path.resolve().parents[2]
    errors: list[str] = []
    roles: dict[str, Path] = {}
    checked = []
    if registry.get("analysis_id") != ANALYSIS_ID:
        errors.append("Unexpected analysis ID")
    if registry.get("status") != STATUS:
        errors.append("Unexpected status")
    for item in registry.get("inputs", []) + registry.get("implementation", []) + registry.get("outputs", []):
        role = str(item.get("role"))
        artifact = resolve(root, item.get("path", ""))
        actual = sha(artifact) if artifact.is_file() else None
        roles[role] = artifact
        checked.append({"role": role, "path": str(artifact), "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"Artifact missing or changed: {role}")
    required = {
        "post_capture_config", "exact_text_result_registry", "builder", "independent_verifier",
        "implementation_tests", "method_documentation", "result_documentation", "analysis_output",
        "independent_qa", "registry_verifier", "registry_verifier_tests",
    }
    missing = sorted(required - roles.keys())
    if missing:
        errors.append(f"Missing required roles: {missing}")
    if not missing:
        live = audit(roles["post_capture_config"], roles["analysis_output"])
        frozen = load(roles["independent_qa"])
        if live.get("status") != "PASS_INDEPENDENT_RECOMPUTATION" or live.get("errors"):
            errors.append("Live independent recomputation failed")
        if frozen.get("status") != "PASS_INDEPENDENT_RECOMPUTATION":
            errors.append("Frozen independent QA status changed")
        if frozen.get("checks", {}).get("record_level_exact_match_count") != 23:
            errors.append("Frozen record match count changed")
    if registry.get("safety_contract") != SAFETY:
        errors.append("Safety contract changed")
    findings = registry.get("findings", {})
    expected = {
        "minimum_content_pass_rows": 22,
        "opened_cohort_rows_compared": 107,
        "opened_exact_or_host_overlap_count": 0,
        "opened_near_duplicate_route_count": 0,
        "candidate_internal_near_duplicate_pairs": 0,
        "transitive_exclusion_groups": 22,
        "cross_target_stratum_transitive_groups": 0,
        "labels_created": 0,
    }
    for key, value in expected.items():
        if findings.get(key) != value:
            errors.append(f"Finding changed: {key}")
    decision = registry.get("decision", {})
    if decision.get("manual_cross_domain_case_clone_and_group_review_allowed") is not True:
        errors.append("Manual group review was not released")
    if decision.get("human_label_review_allowed") is not False:
        errors.append("Human label review must remain blocked")
    return {
        "analysis_id": registry.get("analysis_id"),
        "valid": not errors,
        "status": registry.get("status"),
        "checked_artifact_count": len(checked),
        "minimum_content_pass_rows": 22,
        "transitive_exclusion_groups": 22,
        "manual_cross_domain_case_clone_and_group_review_allowed": True,
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
