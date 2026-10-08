"""Verify the registered bounded manual group-review result V1."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verify_target_text_corpus_v1_manual_group_primary_review import verify


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_registry(path: Path) -> dict:
    registry = load(path)
    root = path.resolve().parents[2]
    errors = []
    roles = {}
    checked = []
    if registry.get("analysis_id") != "ISI_TARGET_TEXT_CORPUS_V1_MANUAL_GROUP_REVIEW_RESULT_V1":
        errors.append("Unexpected analysis ID")
    if registry.get("status") != "FROZEN_MANUAL_GROUP_REVIEW_PASS_22_DISTINCT_14_FLAGGED":
        errors.append("Unexpected status")
    for item in registry.get("inputs", []) + registry.get("implementation", []) + registry.get("outputs", []):
        artifact = Path(str(item.get("path", "")))
        if not artifact.is_absolute():
            artifact = root / artifact
        actual = sha(artifact) if artifact.is_file() else None
        role = str(item.get("role"))
        roles[role] = artifact
        checked.append({"role": role, "path": str(artifact), "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"Artifact missing or changed: {role}")
    required = {
        "manual_review_config", "post_capture_result_registry", "packet_builder", "packet_tests",
        "structural_verifier", "structural_verifier_tests", "method_documentation", "result_documentation",
        "review_packet", "primary_review", "failed_structural_qa_attempt_1", "passing_structural_qa",
        "registry_verifier", "registry_verifier_tests",
    }
    missing = sorted(required - roles.keys())
    if missing:
        errors.append(f"Missing roles: {missing}")
    if not missing:
        live = verify(roles["manual_review_config"], roles["primary_review"])
        if live.get("status") != "PASS_STRUCTURE_AND_SCOPE" or live.get("errors"):
            errors.append("Live structural verification failed")
        frozen = load(roles["passing_structural_qa"])
        failed = load(roles["failed_structural_qa_attempt_1"])
        if frozen.get("status") != "PASS_STRUCTURE_AND_SCOPE":
            errors.append("Frozen passing QA status changed")
        if failed.get("status") != "FAIL":
            errors.append("Preserved first QA attempt is not a failure artifact")
    findings = registry.get("findings", {})
    expected = {
        "reviewed_records": 22, "keep_provisionally_distinct": 22,
        "technical_merges": 0, "opened_cohort_clone_routes": 0,
        "unresolved_group_relationships": 0, "records_with_downstream_flags": 14,
        "labels_created": 0,
    }
    for key, value in expected.items():
        if findings.get(key) != value:
            errors.append(f"Finding changed: {key}")
    if registry.get("decision", {}).get("primary_case_and_artifact_review_allowed") is not True:
        errors.append("Primary review was not released")
    if registry.get("decision", {}).get("binary_labeling_completed") is not False:
        errors.append("Registry incorrectly claims binary labeling")
    return {
        "analysis_id": registry.get("analysis_id"),
        "valid": not errors,
        "status": registry.get("status"),
        "checked_artifact_count": len(checked),
        "reviewed_records": 22,
        "records_with_downstream_flags": 14,
        "primary_case_and_artifact_review_allowed": True,
        "binary_labeling_completed": False,
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
