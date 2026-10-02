"""Verify Target Text Corpus V1 pre-acquisition artifacts and closed gates."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ANALYSIS_ID = "ISI_TARGET_TEXT_CORPUS_V1_PREACQUISITION"
EXPECTED_STATUS = "FROZEN_PREACQUISITION_ARTIFACTS_COMPLETE_CAPTURE_BLOCKED"
INVENTORY_ID = "ISI_TARGET_TEXT_CORPUS_V1_CANDIDATE_SOURCE_INVENTORY"
INDEX_ID = "ISI_TARGET_TEXT_CORPUS_V1_OPENED_EXTERNAL_EXCLUSION_INDEX"
EXPECTED_RECORD_KEYS = {
    "record_exclusion_key",
    "cohort_id",
    "cohort_record_id",
    "case_id",
    "case_or_campaign_group_id",
    "near_duplicate_group_id",
    "artifact_id",
    "source_record_id",
    "source_candidate_id",
    "capture_sha256",
    "text_sha256",
    "exact_text_group_key",
    "normalized_host_sha256",
    "url_sha256",
    "legacy_case_id_missing",
    "legacy_group_identifiers_missing",
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


def is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def verify(registry_path: Path) -> dict[str, Any]:
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
        actual_hash = sha256_file(path) if path.is_file() else None
        if role in role_paths:
            errors.append(f"Duplicate artifact role: {role}")
        role_paths[role] = path
        checked.append({"role": role, "path": str(path), "sha256": actual_hash})
        if actual_hash != item.get("sha256"):
            errors.append(f"Artifact missing or changed: {role}")

    inventory_path = role_paths.get("candidate_source_inventory")
    index_path = role_paths.get("opened_external_exclusion_index")
    inventory: dict[str, Any] = {}
    index: dict[str, Any] = {}
    if inventory_path is None or not inventory_path.is_file():
        errors.append("Candidate-source inventory unavailable")
    else:
        inventory = load_json(inventory_path)
    if index_path is None or not index_path.is_file():
        errors.append("Opened-external exclusion index unavailable")
    else:
        index = load_json(index_path)

    if inventory:
        if inventory.get("inventory_id") != INVENTORY_ID:
            errors.append("Unexpected inventory ID")
        if inventory.get("status") != "FROZEN_PROVENANCE_ONLY_WITH_CHANNEL_GAPS":
            errors.append("Unexpected inventory status")
        if inventory.get("record_count") != 0:
            errors.append("Candidate inventory contains acquired records")
        if len(inventory.get("channels", [])) != 4:
            errors.append("Candidate channel count changed")
        coverage = inventory.get("coverage", {})
        if coverage.get("planned_channels_by_target_status") != {
            "CONFIRMED": 2,
            "LEGITIMATE": 2,
        }:
            errors.append("Planned target-status channel coverage changed")
        if coverage.get("provenance_enumeration_ready_channels_by_target_status") != {
            "CONFIRMED": 1,
            "LEGITIMATE": 1,
        }:
            errors.append("Ready target-status channel coverage changed")
        if coverage.get("channel_gate_passed") is not False:
            errors.append("Candidate channel gate must remain closed")
        if inventory.get("safety_contract", {}).get("artifact_text_emitted") != 0:
            errors.append("Candidate inventory emitted artifact text")

    if index:
        if index.get("index_id") != INDEX_ID:
            errors.append("Unexpected exclusion index ID")
        if index.get("status") != "FROZEN_EXACT_AND_DOMAIN_COMPLETE_LEGACY_GROUP_GAPS_OPEN":
            errors.append("Unexpected exclusion index status")
        expected_counts = {
            "cohorts": 4,
            "opened_records": 107,
            "unique_record_exclusion_keys": 107,
            "records_with_case_id": 21,
            "records_missing_case_id": 86,
            "records_with_case_or_campaign_group_id": 21,
            "records_with_near_duplicate_group_id": 21,
            "records_with_source_candidate_id": 86,
            "unique_capture_sha256": 98,
            "unique_text_sha256": 96,
            "unique_normalized_host_sha256": 94,
        }
        if index.get("counts") != expected_counts:
            errors.append("Exclusion-index counts changed")
        records = index.get("records", [])
        if len(records) != 107:
            errors.append("Exclusion-index record count changed")
        record_keys = [item.get("record_exclusion_key") for item in records]
        if len(record_keys) != len(set(record_keys)):
            errors.append("Duplicate record exclusion keys")
        for item in records:
            if set(item) != EXPECTED_RECORD_KEYS:
                errors.append(f"Record schema changed: {item.get('record_exclusion_key')}")
                break
            for field in ("capture_sha256", "text_sha256", "normalized_host_sha256"):
                if not is_sha256(item.get(field)):
                    errors.append(
                        f"Invalid {field}: {item.get('record_exclusion_key')}"
                    )
                    break
            if "ground_truth_status" in item or "visible_text" in item or "text" in item:
                errors.append(
                    f"Label or artifact text leaked: {item.get('record_exclusion_key')}"
                )
                break
        collisions = index.get("collision_groups", {})
        if len(collisions.get("capture_sha256", [])) != 9:
            errors.append("Capture-collision groups changed")
        if len(collisions.get("text_sha256", [])) != 11:
            errors.append("Text-collision groups changed")
        if len(collisions.get("normalized_host_sha256", [])) != 13:
            errors.append("Normalized-host collision groups changed")
        quality = index.get("quality_gates", {})
        if quality.get("exact_and_normalized_host_exclusion_ready") is not True:
            errors.append("Exact/normalized-host exclusion must be ready")
        if (
            quality.get(
                "case_domain_family_and_normalized_near_duplicate_exclusion_ready"
            )
            is not False
        ):
            errors.append("Legacy group-remediation gate must remain open")
        safety = index.get("safety_contract", {})
        if (
            safety.get("existing_opened_records_processed_offline") != 107
            or safety.get("artifact_text_emitted") != 0
            or safety.get("ground_truth_statuses_emitted") != 0
        ):
            errors.append("Exclusion-index safety counts changed")

    expected_registry_safety = {
        "network_operations": 0,
        "domain_access_allowed": False,
        "new_records_acquired": 0,
        "new_artifact_captures": 0,
        "labels_created": 0,
        "labels_changed": 0,
        "model_fit_operations": 0,
        "model_scoring_operations": 0,
        "validation_or_test_openings": 0,
        "training_allowed": False,
        "deployment_allowed": False,
        "existing_opened_records_processed_offline": 107,
        "artifact_text_emitted": 0,
        "ground_truth_statuses_emitted": 0,
    }
    if registry.get("safety_contract") != expected_registry_safety:
        errors.append("Registry safety contract changed")

    return {
        "analysis_id": registry.get("analysis_id"),
        "valid": not errors,
        "status": registry.get("status"),
        "checked_artifact_count": len(checked),
        "opened_record_count": index.get("counts", {}).get("opened_records"),
        "legacy_case_id_gap_count": index.get("counts", {}).get(
            "records_missing_case_id"
        ),
        "channel_gate_passed": inventory.get("coverage", {}).get(
            "channel_gate_passed"
        ),
        "capture_allowed": False,
        "model_fit_operations": 0,
        "errors": errors,
        "checked": checked,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.registry)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
