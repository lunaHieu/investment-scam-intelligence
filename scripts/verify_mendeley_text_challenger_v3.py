"""Verify the frozen V3 challenger rejection and all closed evaluation gates."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

from mendeley_text_baseline_v2_common import sha256_file


MODEL_ID = "ISI_TEXT_CHALLENGER_V3_STYLE_GUARD_ABLATION"
SELECTION_ID = "MENDELEY_TEXT_CHALLENGER_V3_STYLE_GUARD_SELECTION"
STATUS = "FROZEN_VALIDATION_CHALLENGER_REJECTED_TEST_EXTERNAL_UNOPENED"


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


def canonical_digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def confusion(rows: list[dict], prefix: str) -> dict[str, int]:
    result = {"tn": 0, "fp": 0, "fn": 0, "tp": 0}
    keys = {(0, 0): "tn", (0, 1): "fp", (1, 0): "fn", (1, 1): "tp"}
    for row in rows:
        key = keys.get((row.get("source_label"), row.get(f"{prefix}_prediction")))
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
    expected_roles = {
        "validation_selection", "development_oof_predictions", "validation_predictions"
    }
    if set(outputs) != expected_roles:
        errors.append("Unexpected output roles")
    selection_path = resolve(root, outputs.get("validation_selection", {}).get("path", ""))
    development_path = resolve(root, outputs.get("development_oof_predictions", {}).get("path", ""))
    validation_path = resolve(root, outputs.get("validation_predictions", {}).get("path", ""))
    selection = load_json(selection_path) if selection_path.is_file() else {}
    development = load_jsonl(development_path) if development_path.is_file() else []
    validation = load_jsonl(validation_path) if validation_path.is_file() else []
    if selection.get("selection_id") != SELECTION_ID:
        errors.append("Selection ID mismatch")
    if selection.get("status") != "VALIDATION_CHALLENGER_REJECTED_TEST_EXTERNAL_UNOPENED":
        errors.append("Selection status mismatch")
    for rows, expected_count, stage, partition in (
        (development, 3916, "development_oof", "train"),
        (validation, 838, "validation_confirmation", "validation"),
    ):
        ids = [row.get("record_id") for row in rows]
        if len(rows) != expected_count or len(set(ids)) != expected_count:
            errors.append(f"Expected {expected_count} unique {stage} predictions")
        if any(row.get("stage") != stage or row.get("partition") != partition for row in rows):
            errors.append(f"Unexpected routing in {stage} predictions")
    groups_to_folds: dict[object, set[object]] = defaultdict(set)
    for row in development:
        groups_to_folds[row.get("split_group_id")].add(row.get("development_fold"))
    if len(groups_to_folds) != 3783 or any(len(values) != 1 for values in groups_to_folds.values()):
        errors.append("Development group-to-fold isolation failed")
    if {next(iter(values)) for values in groups_to_folds.values() if values} != {0, 1, 2, 3}:
        errors.append("Unexpected development folds")
    expected_confusions = {
        "development_baseline": {"tn": 1447, "fp": 545, "fn": 597, "tp": 1327},
        "development_challenger": {"tn": 1466, "fp": 526, "fn": 589, "tp": 1335},
        "validation_baseline": {"tn": 308, "fp": 118, "fn": 133, "tp": 279},
        "validation_challenger": {"tn": 294, "fp": 132, "fn": 138, "tp": 274},
    }
    observed_confusions = {
        "development_baseline": confusion(development, "baseline") if development else {},
        "development_challenger": confusion(development, "challenger") if development else {},
        "validation_baseline": confusion(validation, "baseline") if validation else {},
        "validation_challenger": confusion(validation, "challenger") if validation else {},
    }
    if observed_confusions != expected_confusions:
        errors.append(f"Prediction confusion changed: {observed_confusions}")
    representations = selection.get("representations", {})
    baseline = representations.get("word_1_2", {})
    challenger = representations.get("word_1_2_english_stopwords", {})
    expected_metrics = {
        "baseline_dev": 0.708102,
        "challenger_dev": 0.714952,
        "baseline_validation": 0.700118,
        "challenger_validation": 0.677621,
    }
    observed_metrics = {
        "baseline_dev": baseline.get("development_oof", {}).get("metrics", {}).get("macro_f1"),
        "challenger_dev": challenger.get("development_oof", {}).get("metrics", {}).get("macro_f1"),
        "baseline_validation": baseline.get("validation", {}).get("metrics", {}).get("macro_f1"),
        "challenger_validation": challenger.get("validation", {}).get("metrics", {}).get("macro_f1"),
    }
    if observed_metrics != expected_metrics:
        errors.append(f"Frozen Macro-F1 values changed: {observed_metrics}")
    if baseline.get("development_oof", {}).get("metrics", {}).get("confusion_matrix") != expected_confusions["development_baseline"]:
        errors.append("Development baseline confusion does not reproduce")
    if challenger.get("development_oof", {}).get("metrics", {}).get("confusion_matrix") != expected_confusions["development_challenger"]:
        errors.append("Development challenger confusion does not reproduce")
    if baseline.get("validation", {}).get("metrics", {}).get("confusion_matrix") != expected_confusions["validation_baseline"]:
        errors.append("Validation baseline confusion does not reproduce")
    if challenger.get("validation", {}).get("metrics", {}).get("confusion_matrix") != expected_confusions["validation_challenger"]:
        errors.append("Validation challenger confusion does not reproduce")
    expected_stop_words = sorted(ENGLISH_STOP_WORDS)
    if challenger.get("english_stop_words_count") != len(expected_stop_words):
        errors.append("English stop-word count changed")
    if challenger.get("english_stop_words_sha256") != canonical_digest(expected_stop_words):
        errors.append("English stop-word digest changed")
    decision = selection.get("decision", {})
    development_decision = decision.get("development_oof", {})
    validation_decision = decision.get("validation_confirmation", {})
    failed_development = {
        name for name, passed in development_decision.get("gates", {}).items() if not passed
    }
    failed_validation = {
        name for name, passed in validation_decision.get("gates", {}).items() if not passed
    }
    if failed_development != {"within_source_label_shuffle_macro_f1_delta_maximum"}:
        errors.append(f"Unexpected development gate failures: {sorted(failed_development)}")
    if failed_validation != {
        "source_mean_macro_f1_delta_minimum",
        "worst_source_macro_f1_delta_minimum",
        "pooled_macro_f1_delta_minimum",
        "maximum_single_source_macro_f1_decline",
        "source_predictability_macro_f1_delta_maximum",
        "paired_group_bootstrap_macro_f1_delta_ci_lower_minimum",
    }:
        errors.append(f"Unexpected validation gate failures: {sorted(failed_validation)}")
    bootstrap = selection.get("paired_group_bootstrap_validation", {})
    if bootstrap.get("difference_percentile_95_ci") != [-0.042531, -0.003272]:
        errors.append("Validation bootstrap interval changed")
    if (
        decision.get("all_required_gates_passed") is not False
        or decision.get("selected_variant") != "word_1_2"
        or decision.get("internal_test_allowed") is not False
        or decision.get("existing_external_benchmark_allowed") is not False
        or decision.get("challenger_model_artifact_allowed") is not False
    ):
        errors.append("Selection decision gate is open")
    quality = selection.get("quality_gates", {})
    if not quality or not all(value is True for value in quality.values()):
        errors.append("One or more quality gates failed")
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
        "existing_external_benchmark_rows_loaded": 0,
        "existing_external_benchmark_rows_transformed": 0,
        "auxiliary_rows_used": 0,
        "quarantine_rows_used": 0,
        "manual_stop_word_changes": 0,
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
        or registry_decision.get("challenger_model_artifact_created") is not False
        or registry_decision.get("promote_for_deployment") is not False
    ):
        errors.append("Registry decision gate is open")
    print(json.dumps({
        "model_id": registry.get("model_id"),
        "valid": not errors,
        "development_prediction_count": len(development),
        "validation_prediction_count": len(validation),
        "development_group_count": len(groups_to_folds),
        "failed_development_gates": sorted(failed_development),
        "failed_validation_gates": sorted(failed_validation),
        "errors": errors,
        "checked": checked,
    }, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
