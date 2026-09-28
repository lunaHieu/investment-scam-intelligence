"""Verify the frozen Financial Claims V1 validation-ablation registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mendeley_text_baseline_v2_common import sha256_file
from select_mendeley_financial_claims_ablation_v1 import (
    EXPECTED_FEATURE_SHA256,
    EXPECTED_PROTOCOL_SHA256,
)


EXPECTED_SELECTION_SHA256 = "391649445e476e39e7ffadc1552ca0c872312d503d3e92ccc569d56bb0d627b2"


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    args = parser.parse_args()
    registry = load_json(args.registry)
    errors: list[str] = []

    if registry.get("model_id") != "ISI_FINANCIAL_CLAIMS_ABLATION_V1":
        errors.append("Unexpected model ID")
    if registry.get("status") != "FROZEN_VALIDATION_SELECTION_RETAIN_TEXT_ONLY_TEST_UNOPENED":
        errors.append("Registry status is not frozen with test unopened")

    artifacts = registry.get("artifacts", [])
    by_role = {str(item.get("role")): item for item in artifacts}
    expected_roles = {
        "protocol",
        "group_split_dataset",
        "financial_claim_features",
        "validation_selection",
    }
    if set(by_role) != expected_roles or len(artifacts) != len(expected_roles):
        errors.append("Artifact roles are incomplete or duplicated")
    artifact_results = []
    repository_root = args.registry.resolve().parents[2]
    for role in sorted(expected_roles):
        item = by_role.get(role, {})
        path = Path(item.get("path", ""))
        if not path.is_absolute():
            path = repository_root / path
        actual_hash = sha256_file(path) if path.is_file() else None
        if actual_hash != item.get("sha256"):
            errors.append(f"Artifact SHA-256 mismatch: {role}")
        artifact_results.append({"role": role, "path": str(path), "sha256": actual_hash})

    if by_role.get("protocol", {}).get("sha256") != EXPECTED_PROTOCOL_SHA256:
        errors.append("Protocol hash differs from frozen implementation")
    if by_role.get("financial_claim_features", {}).get("sha256") != EXPECTED_FEATURE_SHA256:
        errors.append("Feature hash differs from frozen implementation")
    if by_role.get("validation_selection", {}).get("sha256") != EXPECTED_SELECTION_SHA256:
        errors.append("Selection hash differs from frozen implementation")

    selection_path = Path(by_role.get("validation_selection", {}).get("path", ""))
    selection = load_json(selection_path) if selection_path.is_file() else {}
    if selection.get("status") != "FROZEN_VALIDATION_SELECTION_TEST_UNOPENED":
        errors.append("Selection artifact status is invalid")
    if selection.get("data", {}).get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256:
        errors.append("Selection protocol hash mismatch")
    if selection.get("data", {}).get("feature_artifact_sha256") != EXPECTED_FEATURE_SHA256:
        errors.append("Selection feature hash mismatch")
    decision = selection.get("decision", {})
    if decision.get("selected_variant") != "text_only":
        errors.append("Validation decision must retain text_only")
    if decision.get("passes_all_promotion_gates") is not False:
        errors.append("Failed challenger cannot pass promotion gates")
    if decision.get("test_evaluation_allowed") is not False:
        errors.append("Selection cannot allow test evaluation")
    safety = selection.get("safety_contract", {})
    if safety.get("test_opened") is not False or safety.get("test_predictions_created") is not False:
        errors.append("Test safety contract is open")
    if safety.get("model_artifact_created") is not False:
        errors.append("Selection must not create a model artifact")
    if not selection.get("quality_gates") or not all(selection["quality_gates"].values()):
        errors.append("Selection quality gates did not all pass")

    registry_decision = registry.get("decision", {})
    if registry_decision.get("selected_variant") != "text_only":
        errors.append("Registry decision differs from selection artifact")
    if registry_decision.get("open_internal_test_for_challenger") is not False:
        errors.append("Registry opens test for the failed challenger")
    registry_safety = registry.get("safety_contract", {})
    if registry_safety.get("test_opened") is not False:
        errors.append("Registry test safety gate is open")
    if registry_safety.get("deployment_allowed") is not False:
        errors.append("Registry deployment gate is open")

    result = {
        "model_id": registry.get("model_id"),
        "status": "VALID" if not errors else "INVALID",
        "selected_variant": decision.get("selected_variant"),
        "test_opened": safety.get("test_opened"),
        "artifact_results": artifact_results,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
