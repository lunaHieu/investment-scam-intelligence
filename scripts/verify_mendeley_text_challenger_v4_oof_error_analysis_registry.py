"""Verify the hash-pinned registry for the train-only V4 OOF error analysis."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from mendeley_text_baseline_v2_common import sha256_file  # noqa: E402
from verify_mendeley_text_challenger_v4_oof_error_analysis import (  # noqa: E402
    verify as verify_report,
)


ANALYSIS_ID = "MENDELEY_TEXT_CHALLENGER_V4_TRAIN_OOF_ERROR_ANALYSIS"
EXPECTED_STATUS = "COMPLETE_TRAIN_ONLY_DIAGNOSTIC_NO_MODEL_CHANGE"


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
    checked: list[dict[str, object]] = []
    paths: dict[str, Path] = {}

    if registry.get("analysis_id") != ANALYSIS_ID:
        errors.append("Unexpected registry analysis ID")
    if registry.get("status") != EXPECTED_STATUS:
        errors.append("Unexpected registry status")

    entries = (
        list(registry.get("inputs", []))
        + list(registry.get("implementation", []))
        + list(registry.get("outputs", []))
    )
    for item in entries:
        role = str(item.get("role"))
        path = resolve(root, item.get("path", ""))
        actual_hash = sha256_file(path) if path.is_file() else None
        if role in paths:
            errors.append(f"Duplicate artifact role: {role}")
        paths[role] = path
        checked.append({"role": role, "path": str(path), "sha256": actual_hash})
        if actual_hash != item.get("sha256"):
            errors.append(f"Artifact missing or changed: {role}")

    report_path = paths.get("error_analysis_report")
    report_check: dict[str, Any] = {}
    if report_path is None or not report_path.is_file():
        errors.append("Error-analysis report is unavailable")
    else:
        report_check = verify_report(report_path)
        if not report_check.get("valid"):
            errors.extend(
                f"Report verifier: {message}"
                for message in report_check.get("errors", [])
            )
        report = load_json(report_path)
        expected_findings = {
            "row_count": 3916,
            "group_count": 3783,
            "baseline_error_count": 1091,
            "e5_error_count": 1214,
            "e5_regression_count": 567,
            "e5_recovery_count": 444,
            "net_e5_regression_count": 123,
            "net_e5_regression_rate": 0.03141,
            "nearest_neighbor_same_source_rate": 0.945097,
            "nearest_neighbor_same_label_rate": 0.719356,
            "truncated_row_count": 379,
            "truncated_net_e5_regression_rate": 0.116095,
            "nontruncated_net_e5_regression_rate": 0.022335,
            "review_queue_count": 60,
        }
        if registry.get("findings", {}).get("headline") != expected_findings:
            errors.append("Registry headline findings changed")
        transitions = report.get("transition_summary", {})
        neighbors = report.get("nearest_neighbor_diagnostic", {}).get("all", {})
        truncation = report.get("truncation_diagnostic", {}).get(
            "by_truncated_at_512", {}
        )
        reproduced = {
            "row_count": report.get("scope", {}).get("row_count"),
            "group_count": report.get("scope", {}).get("group_count"),
            "baseline_error_count": transitions.get("baseline_error_count"),
            "e5_error_count": transitions.get("challenger_error_count"),
            "e5_regression_count": transitions.get("transition_counts", {}).get(
                "e5_regression"
            ),
            "e5_recovery_count": transitions.get("transition_counts", {}).get(
                "e5_recovery"
            ),
            "net_e5_regression_count": (
                transitions.get("transition_counts", {}).get("e5_regression", 0)
                - transitions.get("transition_counts", {}).get("e5_recovery", 0)
            ),
            "net_e5_regression_rate": transitions.get("net_e5_regression_rate"),
            "nearest_neighbor_same_source_rate": neighbors.get("same_source_rate"),
            "nearest_neighbor_same_label_rate": neighbors.get("same_label_rate"),
            "truncated_row_count": truncation.get("True", {}).get("row_count"),
            "truncated_net_e5_regression_rate": truncation.get("True", {}).get(
                "net_e5_regression_rate"
            ),
            "nontruncated_net_e5_regression_rate": truncation.get("False", {}).get(
                "net_e5_regression_rate"
            ),
            "review_queue_count": report.get("artifacts", {})
            .get("review_queue", {})
            .get("record_count"),
        }
        if reproduced != expected_findings:
            errors.append("Registry headline findings do not reproduce from report")

    decision = registry.get("decision", {})
    if (
        decision.get("challenger_status") != "REJECTED_AT_DEVELOPMENT_GATE"
        or decision.get("primary_supported_explanation")
        != "SOURCE_STYLE_GEOMETRY_INTERACTING_WITH_WITHIN_SOURCE_LABEL_IMBALANCE"
        or decision.get("truncation_role")
        != "SECONDARY_ASSOCIATED_FACTOR_NOT_CAUSALLY_ESTABLISHED"
        or decision.get("new_model_or_configuration_authorized") is not False
    ):
        errors.append("Registry decision changed or overstates the evidence")

    expected_safety = {
        "network_operations": 0,
        "domain_access_allowed": False,
        "labels_created": 0,
        "new_embedding_operations": 0,
        "encoder_forward_passes": 0,
        "model_fit_operations": 0,
        "model_scoring_operations": 0,
        "validation_rows_used": 0,
        "test_rows_used": 0,
        "external_rows_used": 0,
        "labels_changed": 0,
        "training_eligibility_changes": 0,
        "model_selection_changes": 0,
        "training_allowed": False,
        "deployment_allowed": False,
    }
    if registry.get("safety_contract") != expected_safety:
        errors.append("Registry safety contract changed")

    return {
        "analysis_id": registry.get("analysis_id"),
        "valid": not errors,
        "status": registry.get("status"),
        "checked_artifact_count": len(checked),
        "report_valid": report_check.get("valid", False),
        "validation_opened": False,
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
