"""Verify the frozen V4 challenger registry, artifacts, metrics and closed gates."""

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
from verify_mendeley_text_challenger_v4_development import verify as verify_development  # noqa: E402


MODEL_ID = "ISI_TEXT_CHALLENGER_V4_FROZEN_E5_LINEAR"
STATUS = "FROZEN_DEVELOPMENT_CHALLENGER_REJECTED_VALIDATION_TEST_EXTERNAL_UNOPENED"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def resolve(root: Path, value: Any) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def verify(registry_path: Path) -> dict[str, Any]:
    registry = load_json(registry_path)
    root = registry_path.resolve().parents[2]
    errors: list[str] = []
    checked = []
    if registry.get("model_id") != MODEL_ID:
        errors.append("Unexpected model ID")
    if registry.get("status") != STATUS:
        errors.append("Unexpected registry status")

    entries = (
        list(registry.get("inputs", []))
        + list(registry.get("implementation", []))
        + list(registry.get("outputs", []))
    )
    for entry in entries:
        path = resolve(root, entry.get("path", ""))
        actual = sha256_file(path) if path.is_file() else None
        checked.append({
            "role": entry.get("role"),
            "path": str(path),
            "sha256": actual,
        })
        if actual != entry.get("sha256"):
            errors.append(f"Artifact missing or changed: {entry.get('role')}")
        if entry.get("bytes") is not None and path.is_file() and path.stat().st_size != entry["bytes"]:
            errors.append(f"Artifact size changed: {entry.get('role')}")

    outputs = {entry["role"]: entry for entry in registry.get("outputs", [])}
    expected_output_roles = {
        "train_embedding_cache",
        "train_embedding_metadata",
        "development_oof_result",
        "development_oof_predictions",
    }
    if set(outputs) != expected_output_roles:
        errors.append("Unexpected output roles")

    result_path = resolve(root, outputs.get("development_oof_result", {}).get("path", ""))
    development = verify_development(result_path) if result_path.is_file() else {"valid": False}
    if development.get("valid") is not True:
        errors.append("Independent development verification failed")
    if development.get("baseline_macro_f1") != registry.get("metrics", {}).get("baseline", {}).get(
        "pooled_macro_f1"
    ):
        errors.append("Baseline Macro-F1 registry mismatch")
    if development.get("challenger_macro_f1") != registry.get("metrics", {}).get(
        "challenger", {}
    ).get("pooled_macro_f1"):
        errors.append("Challenger Macro-F1 registry mismatch")

    decision = registry.get("decision", {})
    if (
        decision.get("all_development_gates_passed") is not False
        or decision.get("failed_gate_count") != 6
        or decision.get("selected_variant") != "word_1_2"
        or decision.get("open_validation") is not False
        or decision.get("open_internal_test") is not False
        or decision.get("score_existing_external_benchmarks") is not False
        or decision.get("create_challenger_model_artifact") is not False
        or decision.get("promote_for_deployment") is not False
    ):
        errors.append("Registry decision does not keep all post-development gates closed")

    safety = registry.get("safety_contract", {})
    for key, expected in {
        "validation_rows_used": 0,
        "validation_labels_accessed": 0,
        "validation_scoring_operations": 0,
        "internal_test_rows_used": 0,
        "external_benchmark_rows_used": 0,
        "auxiliary_rows_used": 0,
        "quarantine_rows_used": 0,
        "threshold_changes": 0,
        "model_artifact_created": False,
        "training_allowed": False,
        "deployment_allowed": False,
    }.items():
        if safety.get(key) != expected:
            errors.append(f"Registry safety mismatch: {key}")

    return {
        "model_id": registry.get("model_id"),
        "valid": not errors,
        "status": registry.get("status"),
        "checked_artifact_count": len(checked),
        "development_verification": development,
        "errors": errors,
        "checked": checked,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.registry)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
