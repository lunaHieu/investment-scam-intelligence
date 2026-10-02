"""Verify the rejected V2 text challenger and all unopened evaluation gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mendeley_text_baseline_v2_common import sha256_file


MODEL_ID = "ISI_TEXT_CHALLENGER_V2_VALIDATION_ABLATION"
SELECTION_ID = "MENDELEY_TEXT_CHALLENGER_V2_VALIDATION_SELECTION"
STATUS = "FROZEN_VALIDATION_CHALLENGER_REJECTED_TEST_UNOPENED"


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict[str, object]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line:
            raise ValueError(f"Blank JSONL line: {line_number}")
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"JSONL line is not an object: {line_number}")
        rows.append(value)
    return rows


def resolve(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def confusion(rows: list[dict], prefix: str) -> dict[str, int]:
    result = {"tn": 0, "fp": 0, "fn": 0, "tp": 0}
    for row in rows:
        key = {
            (0, 0): "tn",
            (0, 1): "fp",
            (1, 0): "fn",
            (1, 1): "tp",
        }.get((row.get("source_label"), row.get(f"{prefix}_prediction")))
        if key is None:
            raise ValueError(f"Invalid prediction row: {row.get('record_id')}")
        result[key] += 1
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    args = parser.parse_args()
    registry = load_json(args.registry)
    root = args.registry.resolve().parents[2]
    errors: list[str] = []
    checked = []
    if registry.get("model_id") != MODEL_ID:
        errors.append("Unexpected model ID")
    if registry.get("status") != STATUS:
        errors.append("Unexpected registry status")
    entries = (
        list(registry.get("implementation", []))
        + list(registry.get("inputs", []))
        + list(registry.get("outputs", []))
    )
    for item in entries:
        path = resolve(root, item.get("path", ""))
        actual = sha256_file(path) if path.is_file() else None
        checked.append({"role": item.get("role"), "path": str(path), "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"Artifact missing or changed: {item.get('role')}")
    outputs = {item.get("role"): item for item in registry.get("outputs", [])}
    if set(outputs) != {"validation_selection", "validation_predictions"}:
        errors.append("Unexpected output roles")
    selection_path = resolve(root, outputs.get("validation_selection", {}).get("path", ""))
    predictions_path = resolve(root, outputs.get("validation_predictions", {}).get("path", ""))
    selection = load_json(selection_path) if selection_path.is_file() else {}
    predictions = load_jsonl(predictions_path) if predictions_path.is_file() else []
    if selection.get("selection_id") != SELECTION_ID:
        errors.append("Selection ID mismatch")
    if selection.get("status") != "VALIDATION_CHALLENGER_REJECTED_TEST_UNOPENED":
        errors.append("Selection status mismatch")
    ids = [item.get("record_id") for item in predictions]
    groups = [item.get("split_group_id") for item in predictions]
    if len(predictions) != 838 or len(set(ids)) != 838:
        errors.append("Expected 838 unique validation predictions")
    if any(item.get("partition") != "validation" for item in predictions):
        errors.append("Prediction output contains a non-validation row")
    if not all(groups):
        errors.append("Prediction output has a missing split group")
    baseline_confusion = confusion(predictions, "baseline") if predictions else {}
    challenger_confusion = confusion(predictions, "challenger") if predictions else {}
    expected_baseline = {"tn": 308, "fp": 118, "fn": 133, "tp": 279}
    expected_challenger = {"tn": 308, "fp": 118, "fn": 126, "tp": 286}
    if baseline_confusion != expected_baseline:
        errors.append(f"Unexpected baseline confusion: {baseline_confusion}")
    if challenger_confusion != expected_challenger:
        errors.append(f"Unexpected challenger confusion: {challenger_confusion}")
    representations = selection.get("representations", {})
    baseline = representations.get("word_1_2", {})
    challenger = representations.get("word_1_2_plus_char_wb_3_5", {})
    if baseline.get("validation", {}).get("confusion_matrix") != baseline_confusion:
        errors.append("Baseline confusion does not reproduce")
    if challenger.get("validation", {}).get("confusion_matrix") != challenger_confusion:
        errors.append("Challenger confusion does not reproduce")
    if baseline.get("validation", {}).get("macro_f1") != 0.700118:
        errors.append("Frozen baseline validation metric changed")
    if challenger.get("validation", {}).get("macro_f1") != 0.70863:
        errors.append("Frozen challenger validation metric changed")
    decision = selection.get("decision", {})
    expected_observed = {
        "source_mean_macro_f1_delta": 0.007699,
        "worst_source_macro_f1_delta": 0.012655,
        "pooled_macro_f1_delta": 0.008512,
        "maximum_single_source_macro_f1_decline": 0.013002,
        "source_predictability_macro_f1_delta": 0.045508,
        "within_source_label_shuffle_macro_f1_delta": 0.001747,
        "paired_group_bootstrap_macro_f1_delta_ci_lower": -0.007058,
    }
    if decision.get("observed") != expected_observed:
        errors.append("Observed promotion values changed")
    failed_gates = {name for name, passed in decision.get("gates", {}).items() if not passed}
    expected_failed = {
        "source_mean_macro_f1_delta_minimum",
        "source_predictability_macro_f1_delta_maximum",
        "paired_group_bootstrap_macro_f1_delta_ci_lower_minimum",
    }
    if failed_gates != expected_failed:
        errors.append(f"Unexpected failed gates: {sorted(failed_gates)}")
    if (
        decision.get("all_gates_passed") is not False
        or decision.get("selected_variant") != "word_1_2"
        or decision.get("internal_test_allowed") is not False
        or decision.get("external_benchmark_allowed") is not False
        or decision.get("challenger_model_artifact_allowed") is not False
    ):
        errors.append("Selection decision gate is open")
    quality = selection.get("quality_gates", {})
    if not quality or not all(value is True for value in quality.values()):
        errors.append("One or more selection quality gates failed")
    access = selection.get("data", {}).get("data_access", {})
    if (
        access.get("loaded_text_rows", {}).get("test") != 0
        or access.get("test_text_transformed") != 0
        or access.get("test_labels_used") != 0
        or access.get("excluded_rows_used") != 0
    ):
        errors.append("Prohibited split data were accessed")
    safety = selection.get("safety_contract", {})
    for key, expected in {
        "network_operations": 0,
        "internal_test_rows_loaded": 0,
        "internal_test_rows_transformed": 0,
        "external_benchmark_rows_loaded": 0,
        "external_benchmark_rows_transformed": 0,
        "auxiliary_rows_used": 0,
        "quarantine_rows_used": 0,
        "threshold_changes": 0,
        "model_artifact_created": False,
        "deployment_allowed": False,
    }.items():
        if safety.get(key) != expected:
            errors.append(f"Selection safety mismatch: {key}")
    registry_decision = registry.get("decision", {})
    if (
        registry_decision.get("selected_variant") != "word_1_2"
        or registry_decision.get("open_internal_test") is not False
        or registry_decision.get("score_existing_external_benchmarks") is not False
        or registry_decision.get("promote_for_deployment") is not False
    ):
        errors.append("Registry decision gate is open")
    registry_safety = registry.get("safety_contract", {})
    for key, expected in {
        "network_operations": 0,
        "test_rows_used": 0,
        "external_benchmark_rows_used": 0,
        "auxiliary_rows_used": 0,
        "quarantine_rows_used": 0,
        "model_artifact_created": False,
        "training_allowed": False,
        "deployment_allowed": False,
    }.items():
        if registry_safety.get(key) != expected:
            errors.append(f"Registry safety mismatch: {key}")
    print(json.dumps({
        "model_id": registry.get("model_id"),
        "valid": not errors,
        "prediction_count": len(predictions),
        "unique_group_count": len(set(groups)),
        "failed_promotion_gates": sorted(failed_gates),
        "errors": errors,
        "checked": checked,
    }, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
