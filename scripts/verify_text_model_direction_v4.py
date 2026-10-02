"""Verify the hash-pinned no-training text-model direction V4 synthesis."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.normalization.external_references import sha256_file


ANALYSIS_ID = "ISI_TEXT_MODEL_DIRECTION_V4_EVIDENCE_SYNTHESIS"
EXPECTED_STATUS = "EVIDENCE_SYNTHESIS_COMPLETE_HYPOTHESIS_ONLY_NO_MODEL_SELECTION"


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def resolve(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    args = parser.parse_args()
    registry = load_json(args.registry)
    root = args.registry.resolve().parents[2]
    errors: list[str] = []
    checked = []
    if registry.get("analysis_id") != ANALYSIS_ID or registry.get("status") != EXPECTED_STATUS:
        errors.append("Unexpected registry identity or status")
    entries = list(registry.get("implementation", [])) + list(registry.get("inputs", [])) + list(registry.get("outputs", []))
    paths: dict[str, Path] = {}
    for item in entries:
        role = str(item.get("role"))
        path = resolve(root, item.get("path", ""))
        actual = sha256_file(path) if path.is_file() else None
        if role in paths:
            errors.append(f"Duplicate role: {role}")
        paths[role] = path
        checked.append({"role": role, "path": str(path), "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"Artifact missing or changed: {role}")
    output = load_json(paths["evidence_synthesis"]) if paths.get("evidence_synthesis", Path()).is_file() else {}
    if output.get("analysis_id") != ANALYSIS_ID or output.get("status") != EXPECTED_STATUS:
        errors.append("Synthesis output identity or status mismatch")
    aggregate = output.get("baseline_evidence", {}).get("cross_cohort_descriptive_aggregate", {})
    if aggregate != {
        "descriptive_only_not_a_pooled_preregistered_benchmark": True,
        "row_count": 68,
        "confusion_matrix": {"tn": 20, "fp": 14, "fn": 7, "tp": 27},
        "accuracy": 0.691176,
        "balanced_accuracy": 0.691176,
        "macro_f1": 0.687869,
    }:
        errors.append(f"Unexpected descriptive aggregate: {aggregate}")
    recurring = output.get("recurring_external_failure_profile", {})
    expected_recurring = {
        "external_record_count": 68,
        "external_error_count": 21,
        "false_positive_count": 14,
        "false_negative_count": 7,
        "near_threshold_record_count": 28,
        "nearest_spam_email_count": 50,
        "nearest_spam_email_error_count": 15,
        "error_rate": 0.308824,
        "near_threshold_rate": 0.411765,
        "nearest_spam_email_rate": 0.735294,
        "nearest_spam_email_error_rate": 0.714286,
    }
    if recurring != expected_recurring:
        errors.append(f"Unexpected recurring failure profile: {recurring}")
    retired = {item.get("direction"): item.get("decision") for item in output.get("retired_directions", [])}
    if retired != {
        "word_plus_character_fragments": "REJECTED_DO_NOT_ITERATE_ON_CURRENT_VALIDATION",
        "english_stopword_removal": "REJECTED_DO_NOT_ITERATE_ON_CURRENT_VALIDATION",
    }:
        errors.append("Retired representation directions are incomplete")
    decision = output.get("decision", {})
    if (
        decision.get("bottleneck") != "DATA_AND_SOURCE_ROBUSTNESS_BEFORE_MODEL_CAPACITY"
        or decision.get("retain_current_frozen_baseline") is not True
        or decision.get("deploy_current_baseline") is not False
        or decision.get("train_an_agentic_or_large_generative_model_now") is not False
        or decision.get("next_hypothesis_family") != "FROZEN_SEMANTIC_SENTENCE_EMBEDDINGS_PLUS_REGULARIZED_LINEAR_CLASSIFIER"
    ):
        errors.append("Research direction decision mismatch")
    if output.get("not_selected_yet") != {
        "exact_encoder": None,
        "embedding_dimension": None,
        "classifier_hyperparameters": None,
        "threshold": None,
        "reason": "Those choices require a separate pre-training protocol and dependency/license audit; this synthesis is not model selection.",
    }:
        errors.append("Synthesis prematurely selects model details")
    for key, expected in {
        "model_fit_operations": 0,
        "model_scoring_operations": 0,
        "external_benchmark_transform_operations": 0,
        "threshold_changes": 0,
        "labels_changed": 0,
        "training_allowed": False,
        "deployment_allowed": False,
    }.items():
        if output.get("safety_contract", {}).get(key) != expected:
            errors.append(f"Synthesis safety contract mismatch: {key}")
        if registry.get("safety_contract", {}).get(key) != expected:
            errors.append(f"Registry safety contract mismatch: {key}")
    print(json.dumps({
        "analysis_id": registry.get("analysis_id"),
        "valid": not errors,
        "errors": errors,
        "decision": decision,
        "checked": checked,
    }, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
