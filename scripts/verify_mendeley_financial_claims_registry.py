"""Verify frozen hashes and gates for a versioned Mendeley Financial Claims registry."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from extract_mendeley_financial_claims import SUPPORTED_FEATURE_VERSIONS, rule_set_sha256


def load_json(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as file:
        value = json.load(file)
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    args = parser.parse_args()
    registry = load_json(args.registry)
    errors: list[str] = []
    feature_version = str(registry.get("feature_set_id", ""))
    if feature_version not in SUPPORTED_FEATURE_VERSIONS:
        raise ValueError(f"Unsupported feature version: {feature_version}")

    source = registry.get("source", {})
    input_path = Path(source.get("input_path", ""))
    if not input_path.is_file():
        errors.append(f"Missing input: {input_path}")
    elif sha256_file(input_path) != source.get("input_sha256"):
        errors.append("Input group-split SHA-256 mismatch")

    expected_roles = {"feature_records", "profile", "review_queue"}
    artifacts = registry.get("artifacts", [])
    actual_roles = {artifact.get("role") for artifact in artifacts}
    if actual_roles != expected_roles or len(artifacts) != len(expected_roles):
        errors.append("Artifact roles are incomplete or duplicated")
    artifact_results = []
    by_role: dict[str, Path] = {}
    for artifact in artifacts:
        role = str(artifact.get("role"))
        path = Path(artifact.get("path", ""))
        by_role[role] = path
        actual_hash = sha256_file(path) if path.is_file() else None
        if actual_hash != artifact.get("sha256"):
            errors.append(f"Artifact SHA-256 mismatch: {role}")
        artifact_results.append({"role": role, "path": str(path), "sha256": actual_hash})

    profile = load_json(by_role["profile"]) if by_role.get("profile", Path()).is_file() else {}
    scope = registry.get("scope", {})
    profile_registry = registry.get("profile", {})
    output_contract = registry.get("output_contract", {})
    review_queue = registry.get("review_queue", {})
    training_gate = registry.get("training_gate", {})

    if registry.get("method", {}).get("rule_set_sha256") != rule_set_sha256(feature_version):
        errors.append("Current rule set differs from frozen registry")
    if profile.get("feature_version") != feature_version:
        errors.append("Profile feature version mismatch")
    if profile.get("rule_set_sha256") != rule_set_sha256(feature_version):
        errors.append("Profile rule fingerprint mismatch")
    if profile.get("processed_record_count") != scope.get("processed_record_count"):
        errors.append("Processed count differs between profile and registry")
    if profile.get("candidate_record_count") != profile_registry.get("candidate_record_count"):
        errors.append("Candidate count differs between profile and registry")
    if profile.get("signal_record_counts") != profile_registry.get("signal_record_counts"):
        errors.append("Signal counts differ between profile and registry")
    if profile.get("review_queue_record_count") != review_queue.get("record_count"):
        errors.append("Review queue count mismatch")
    if profile.get("review_queue_unique_group_count") != review_queue.get("unique_split_group_count"):
        errors.append("Review queue group count mismatch")
    if profile.get("test_partition_text_processed") != 0 or scope.get("test_partition_text_processed") != 0:
        errors.append("Frozen test partition was processed")
    if profile.get("source_labels_used_for_extraction") is not False:
        errors.append("Source-label extraction gate is open")
    if output_contract.get("label_fields") != [] or output_contract.get("source_label_emitted") is not False:
        errors.append("Output label contract is invalid")
    if output_contract.get("network_operations") != 0 or output_contract.get("raw_files_modified") is not False:
        errors.append("Offline/raw immutability contract is invalid")
    if training_gate.get("binary_classifier_allowed") is not False:
        errors.append("Training gate must remain closed")

    result = {
        "feature_set_id": registry.get("feature_set_id"),
        "status": "VALID" if not errors else "INVALID",
        "test_partition_text_processed": profile.get("test_partition_text_processed"),
        "training_allowed": training_gate.get("binary_classifier_allowed"),
        "artifact_results": artifact_results,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
