"""Verify the frozen Target Text Corpus V1 contract and its hash-pinned registry."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ANALYSIS_ID = "ISI_TARGET_TEXT_CORPUS_V1_PROTOCOL"
PROTOCOL_ID = "ISI_TARGET_TEXT_CORPUS_V1"
EXPECTED_STATUS = "FROZEN_PROTOCOL_READY_NO_ACQUISITION_OR_TRAINING"
EXPECTED_PROTOCOL_STATUS = "FROZEN_BEFORE_NEW_TARGET_DATA_ACQUISITION"


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


def _check_equal(errors: list[str], actual: object, expected: object, label: str) -> None:
    if actual != expected:
        errors.append(f"{label} changed: expected {expected!r}, got {actual!r}")


def verify(registry_path: Path) -> dict[str, Any]:
    registry = load_json(registry_path)
    root = registry_path.resolve().parents[2]
    errors: list[str] = []
    checked: list[dict[str, object]] = []
    role_paths: dict[str, Path] = {}

    _check_equal(errors, registry.get("analysis_id"), ANALYSIS_ID, "analysis ID")
    _check_equal(errors, registry.get("status"), EXPECTED_STATUS, "registry status")

    artifacts = (
        list(registry.get("inputs", []))
        + list(registry.get("implementation", []))
        + list(registry.get("outputs", []))
    )
    for item in artifacts:
        role = str(item.get("role"))
        path = resolve(root, item.get("path", ""))
        actual_hash = sha256_file(path) if path.is_file() else None
        if role in role_paths:
            errors.append(f"Duplicate artifact role: {role}")
        role_paths[role] = path
        checked.append({"role": role, "path": str(path), "sha256": actual_hash})
        if actual_hash != item.get("sha256"):
            errors.append(f"Artifact missing or changed: {role}")

    protocol_path = role_paths.get("target_corpus_protocol")
    protocol: dict[str, Any] = {}
    if protocol_path is None or not protocol_path.is_file():
        errors.append("Target corpus protocol unavailable")
    else:
        protocol = load_json(protocol_path)
        _check_equal(errors, protocol.get("protocol_id"), PROTOCOL_ID, "protocol ID")
        _check_equal(
            errors,
            protocol.get("status"),
            EXPECTED_PROTOCOL_STATUS,
            "protocol status",
        )

        for item in list(protocol.get("basis", [])) + list(
            protocol.get("source_role_contract", {})
            .get("opened_external_cohorts", {})
            .get("registries", [])
        ):
            path = resolve(root, item.get("path", ""))
            if not path.is_file() or sha256_file(path) != item.get("sha256"):
                errors.append(f"Protocol dependency missing or changed: {item.get('path')}")

        task = protocol.get("target_task", {})
        _check_equal(
            errors,
            task.get("prediction_unit"),
            "ARTIFACT_WITH_CASE_LEVEL_GROUND_TRUTH",
            "prediction unit",
        )
        _check_equal(
            errors,
            task.get("positive_target", {}).get("required_case_status"),
            "CONFIRMED",
            "positive status",
        )
        _check_equal(
            errors,
            task.get("negative_target", {}).get("required_case_status"),
            "LEGITIMATE",
            "negative status",
        )
        if "excluded from binary fitting" not in str(task.get("uncertain_policy", "")):
            errors.append("UNCERTAIN exclusion policy changed")

        sources = protocol.get("source_role_contract", {})
        _check_equal(
            errors,
            sources.get("mendeley_v2", {}).get("rows_allowed_in_new_target_corpus"),
            0,
            "Mendeley target-corpus allowance",
        )
        _check_equal(
            errors,
            sources.get("opened_external_cohorts", {}).get(
                "rows_allowed_in_training_or_model_selection"
            ),
            0,
            "opened-cohort training allowance",
        )

        review = protocol.get("review_contract", {})
        for key in (
            "primary_review_required_for_every_record",
            "independent_second_review_required_for_every_binary_eligible_record",
            "second_reviewer_must_not_receive_first_review_rationale",
            "owner_acceptance_required_before_eligibility",
        ):
            _check_equal(errors, review.get(key), True, f"review gate {key}")

        gates = protocol.get("minimum_data_gates", {})
        pilot = gates.get("schema_and_review_pilot", {})
        _check_equal(errors, pilot.get("minimum_confirmed_groups"), 20, "pilot positives")
        _check_equal(errors, pilot.get("minimum_legitimate_groups"), 20, "pilot negatives")
        _check_equal(errors, pilot.get("model_training_allowed"), False, "pilot training")

        development = gates.get("development_corpus", {})
        _check_equal(errors, development.get("minimum_confirmed_groups"), 120, "development positives")
        _check_equal(errors, development.get("minimum_legitimate_groups"), 120, "development negatives")
        _check_equal(errors, development.get("minimum_total_groups"), 240, "development total")
        _check_equal(
            errors,
            development.get("minimum_groups_per_label_by_partition"),
            {"train": 84, "validation": 18, "internal_test": 18},
            "partition minimums",
        )
        _check_equal(
            errors,
            development.get("minimum_independent_second_review_coverage"),
            1.0,
            "second-review coverage",
        )

        holdout = gates.get("untouched_external_holdout", {})
        _check_equal(errors, holdout.get("minimum_confirmed_groups"), 30, "holdout positives")
        _check_equal(errors, holdout.get("minimum_legitimate_groups"), 30, "holdout negatives")
        _check_equal(errors, holdout.get("minimum_total_groups"), 60, "holdout total")
        _check_equal(
            errors,
            holdout.get("must_use_separate_acquisition_wave"),
            True,
            "holdout acquisition isolation",
        )

        current = protocol.get("current_gate_status", {})
        _check_equal(errors, current.get("new_target_records_acquired_after_freeze"), 0, "new records")
        _check_equal(errors, current.get("model_training_allowed"), False, "current training gate")

    expected_safety = {
        "network_operations": 0,
        "domain_access_allowed": False,
        "new_records_acquired": 0,
        "labels_created": 0,
        "labels_changed": 0,
        "training_eligibility_changes": 0,
        "model_fit_operations": 0,
        "model_scoring_operations": 0,
        "validation_or_test_openings": 0,
        "training_allowed": False,
        "deployment_allowed": False,
    }
    _check_equal(errors, protocol.get("safety_contract", {}), expected_safety, "protocol safety")
    _check_equal(errors, registry.get("safety_contract", {}), expected_safety, "registry safety")

    return {
        "analysis_id": registry.get("analysis_id"),
        "valid": not errors,
        "status": registry.get("status"),
        "checked_artifact_count": len(checked),
        "protocol_dependency_count": len(protocol.get("basis", []))
        + len(
            protocol.get("source_role_contract", {})
            .get("opened_external_cohorts", {})
            .get("registries", [])
        ),
        "new_records_acquired": protocol.get("safety_contract", {}).get(
            "new_records_acquired"
        ),
        "model_fit_operations": protocol.get("safety_contract", {}).get(
            "model_fit_operations"
        ),
        "validation_or_test_openings": protocol.get("safety_contract", {}).get(
            "validation_or_test_openings"
        ),
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

