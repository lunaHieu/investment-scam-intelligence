"""Verify the frozen no-training text-task and source-role audit V1."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_ID = "ISI_TEXT_TASK_SOURCE_AUDIT_V1"
EXPECTED_STATUS = "FROZEN_SOURCE_ROLE_AUDIT_COMPLETE_NO_CORPUS_OR_MODEL_CHANGE"


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


def verify(registry_path: Path) -> dict[str, Any]:
    registry = load_json(registry_path)
    root = registry_path.resolve().parents[2]
    errors: list[str] = []
    paths: dict[str, Path] = {}
    checked: list[dict[str, object]] = []

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
        if role in paths:
            errors.append(f"Duplicate role: {role}")
        paths[role] = path
        checked.append({"role": role, "path": str(path), "sha256": actual_hash})
        if actual_hash != item.get("sha256"):
            errors.append(f"Artifact missing or changed: {role}")

    output_path = paths.get("audit_result")
    output: dict[str, Any] = {}
    if output_path is None or not output_path.is_file():
        errors.append("Audit output unavailable")
    else:
        output = load_json(output_path)
        if output.get("analysis_id") != ANALYSIS_ID or output.get("status") != EXPECTED_STATUS:
            errors.append("Audit output identity or status mismatch")
        if output.get("dataset_contract") != {
            "label_semantics": "Mendeley V2 harmonized deceptive/suspicious source label; not verified investment-scam ground truth",
            "raw_rows": 16202,
            "benchmark_rows": 5592,
            "train_rows": 3916,
            "validation_rows": 838,
            "test_rows": 838,
            "auxiliary_rows": 10607,
            "quarantine_rows": 3,
            "benchmark_sources": [
                "cresci_stock_2018",
                "phishing",
                "spam_email",
                "twitter_bot_detection",
            ],
        }:
            errors.append("Dataset contract changed")
        evidence = output.get("existing_evidence", {})
        if evidence.get("baseline_error_concentration") != {
            "all_errors": 246,
            "twitter_errors": 208,
            "twitter_share_of_errors": 0.845528,
            "short_errors_lte_12_tokens": 192,
        }:
            errors.append("Baseline error evidence changed")
        shortcuts = evidence.get("source_shortcut_diagnostics", {})
        if shortcuts != {
            "metadata_missingness_test_source_accuracy": 0.934541,
            "source_majority_label_test_accuracy": 0.760395,
            "frozen_e5_source_predictability_macro_f1": 0.932908,
            "frozen_e5_nearest_neighbor_same_source_rate": 0.945097,
            "frozen_e5_net_regression_rate": 0.03141,
        }:
            errors.append("Source-shortcut evidence changed")

        roles = output.get("source_role_recommendations", {})
        if set(roles) != {
            "cresci_stock_2018",
            "phishing",
            "spam_email",
            "twitter_bot_detection",
            "fake_profile_post",
            "conflicting_phishing_component",
        }:
            errors.append("Source-role coverage changed")
        elif any(item.get("use_as_final_target_domain_ground_truth") is not False for item in roles.values()):
            errors.append("Audit improperly promotes a Mendeley source to final ground truth")
        if roles.get("twitter_bot_detection", {}).get("recommended_role") != "ACCOUNT_OR_BEHAVIOR_AUXILIARY_TASK":
            errors.append("Twitter source role changed")

        decision = output.get("decision", {})
        if (
            decision.get("primary_task_misalignment_found") is not True
            or decision.get("mendeley_group_split_v2_role")
            != "HISTORICAL_HETEROGENEOUS_BENCHMARK"
            or decision.get("remove_or_relabel_existing_rows_now") is not False
            or decision.get("train_another_model_now") is not False
            or decision.get("new_model_or_corpus_configuration_authorized") is not False
        ):
            errors.append("Audit decision changed")

    expected_safety = {
        "network_operations": 0,
        "domain_access_allowed": False,
        "labels_created": 0,
        "new_row_level_data_access": 0,
        "model_fit_operations": 0,
        "model_scoring_operations": 0,
        "labels_changed": 0,
        "split_changes": 0,
        "training_eligibility_changes": 0,
        "validation_or_test_openings": 0,
        "training_allowed": False,
        "deployment_allowed": False,
    }
    if registry.get("safety_contract") != expected_safety:
        errors.append("Registry safety contract changed")
    output_safety = output.get("safety_contract", {})
    for key, expected in {
        "new_row_level_data_access": 0,
        "model_fit_operations": 0,
        "model_scoring_operations": 0,
        "labels_changed": 0,
        "split_changes": 0,
        "training_eligibility_changes": 0,
        "validation_or_test_openings": 0,
        "training_allowed": False,
        "deployment_allowed": False,
    }.items():
        if output_safety.get(key) != expected:
            errors.append(f"Output safety mismatch: {key}")

    return {
        "analysis_id": registry.get("analysis_id"),
        "valid": not errors,
        "status": registry.get("status"),
        "checked_artifact_count": len(checked),
        "source_role_count": len(output.get("source_role_recommendations", {})),
        "model_fit_operations": 0,
        "validation_or_test_openings": 0,
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

