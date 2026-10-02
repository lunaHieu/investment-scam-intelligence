"""Synthesize frozen V2/V3 evidence into a no-training V4 research direction."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.normalization.external_references import sha256_file


EXPECTED_ROLES = {
    "baseline_registry",
    "character_challenger_registry",
    "stopword_challenger_registry",
    "wayback_v2_evaluation_registry",
    "wayback_v2_error_registry",
    "wayback_v3_evaluation_registry",
    "wayback_v3_error_registry",
}


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def resolve(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else ROOT / path


def class_f1(tp: int, fp: int, fn: int) -> float:
    denominator = 2 * tp + fp + fn
    return 0.0 if denominator == 0 else 2 * tp / denominator


def aggregate_external(v2: dict[str, object], v3: dict[str, object]) -> dict[str, object]:
    c2 = v2["metrics"]["confusion_matrix"]
    c3 = v3["metrics"]["confusion_matrix"]
    confusion = {key: int(c2[key]) + int(c3[key]) for key in ("tn", "fp", "fn", "tp")}
    row_count = sum(confusion.values())
    accuracy = (confusion["tn"] + confusion["tp"]) / row_count
    recall_0 = confusion["tn"] / (confusion["tn"] + confusion["fp"])
    recall_1 = confusion["tp"] / (confusion["tp"] + confusion["fn"])
    f1_0 = class_f1(confusion["tn"], confusion["fn"], confusion["fp"])
    f1_1 = class_f1(confusion["tp"], confusion["fp"], confusion["fn"])
    return {
        "descriptive_only_not_a_pooled_preregistered_benchmark": True,
        "row_count": row_count,
        "confusion_matrix": confusion,
        "accuracy": round(accuracy, 6),
        "balanced_accuracy": round((recall_0 + recall_1) / 2, 6),
        "macro_f1": round((f1_0 + f1_1) / 2, 6),
    }


def validate_inputs(config: dict[str, object]) -> dict[str, dict[str, object]]:
    items = config.get("inputs", [])
    roles = {str(item["role"]): item for item in items}
    if len(roles) != len(items) or set(roles) != EXPECTED_ROLES:
        raise ValueError("Synthesis input roles are incomplete or duplicated")
    loaded: dict[str, dict[str, object]] = {}
    for role, item in roles.items():
        path = resolve(str(item["path"]))
        if sha256_file(path) != item["sha256"]:
            raise ValueError(f"Frozen synthesis input changed: {role}")
        loaded[role] = load_json(path)
    if loaded["baseline_registry"].get("model_id") != "ISI_TEXT_BASELINE_V2":
        raise ValueError("Unexpected baseline registry")
    if loaded["character_challenger_registry"].get("decision", {}).get("challenger_passes_all_promotion_gates") is not False:
        raise ValueError("Character challenger is not frozen as rejected")
    if loaded["stopword_challenger_registry"].get("decision", {}).get("challenger_passes_all_promotion_gates") is not False:
        raise ValueError("Stop-word challenger is not frozen as rejected")
    if loaded["wayback_v2_error_registry"].get("status") != "FROZEN_WAYBACK_LANGUAGE_V2_DIAGNOSTIC_COMPLETE_NO_TUNING":
        raise ValueError("Wayback V2 diagnostic is not frozen")
    if loaded["wayback_v3_error_registry"].get("status") != "FROZEN_WAYBACK_HOLDOUT_V3_DIAGNOSTIC_COMPLETE_NO_TUNING":
        raise ValueError("Wayback V3 diagnostic is not frozen")
    return loaded


def build_synthesis(config: dict[str, object], loaded: dict[str, dict[str, object]]) -> dict[str, object]:
    baseline = loaded["baseline_registry"]
    char = loaded["character_challenger_registry"]
    stop = loaded["stopword_challenger_registry"]
    v2 = loaded["wayback_v2_evaluation_registry"]
    v2e = loaded["wayback_v2_error_registry"]
    v3 = loaded["wayback_v3_evaluation_registry"]
    v3e = loaded["wayback_v3_error_registry"]
    f2 = v2e["findings"]
    f3 = v3e["findings"]
    aggregate = aggregate_external(v2, v3)
    total_errors = int(f2["error_count"]) + int(f3["error_count"])
    recurring = {
        "external_record_count": int(f2["record_count"]) + int(f3["record_count"]),
        "external_error_count": total_errors,
        "false_positive_count": int(f2["false_positive_count"]) + int(f3["false_positive_count"]),
        "false_negative_count": int(f2["false_negative_count"]) + int(f3["false_negative_count"]),
        "near_threshold_record_count": int(f2["records_within_0_10_of_threshold"]) + int(f3["records_within_0_10_of_threshold"]),
        "nearest_spam_email_count": int(f2["nearest_fit_spam_email_count_all_records"]) + int(f3["nearest_fit_spam_email_count_all_records"]),
        "nearest_spam_email_error_count": int(f2["nearest_fit_spam_email_count_errors"]) + int(f3["nearest_fit_spam_email_count_errors"]),
    }
    recurring["error_rate"] = round(recurring["external_error_count"] / recurring["external_record_count"], 6)
    recurring["near_threshold_rate"] = round(recurring["near_threshold_record_count"] / recurring["external_record_count"], 6)
    recurring["nearest_spam_email_rate"] = round(recurring["nearest_spam_email_count"] / recurring["external_record_count"], 6)
    recurring["nearest_spam_email_error_rate"] = round(recurring["nearest_spam_email_error_count"] / total_errors, 6)
    return {
        "analysis_id": "ISI_TEXT_MODEL_DIRECTION_V4_EVIDENCE_SYNTHESIS",
        "created_at": "2026-10-02",
        "status": "EVIDENCE_SYNTHESIS_COMPLETE_HYPOTHESIS_ONLY_NO_MODEL_SELECTION",
        "inputs": config["inputs"],
        "baseline_evidence": {
            "internal_validation_macro_f1": baseline["metrics"]["validation"]["macro_f1"],
            "internal_test_macro_f1": baseline["metrics"]["test"]["macro_f1"],
            "validation_source_predictability_macro_f1": char["validation_metrics"]["baseline"]["source_predictability_macro_f1"],
            "wayback_v2_macro_f1": v2["metrics"]["macro_f1"],
            "wayback_v3_macro_f1": v3["metrics"]["macro_f1"],
            "wayback_v3_bootstrap_macro_f1_95_percent": v3["metrics"]["bootstrap_95_percent"]["macro_f1"],
            "cross_cohort_descriptive_aggregate": aggregate,
        },
        "recurring_external_failure_profile": recurring,
        "retired_directions": [
            {
                "direction": "word_plus_character_fragments",
                "decision": "REJECTED_DO_NOT_ITERATE_ON_CURRENT_VALIDATION",
                "evidence": {
                    "source_mean_macro_f1_delta": char["validation_metrics"]["challenger_minus_baseline"]["source_mean_macro_f1"],
                    "source_predictability_macro_f1_delta": char["validation_metrics"]["challenger_minus_baseline"]["source_predictability_macro_f1"],
                    "bootstrap_95_percent": char["validation_metrics"]["paired_group_bootstrap"]["difference_percentile_95_ci"],
                },
            },
            {
                "direction": "english_stopword_removal",
                "decision": "REJECTED_DO_NOT_ITERATE_ON_CURRENT_VALIDATION",
                "evidence": {
                    "validation_macro_f1_delta": stop["validation_confirmation_metrics"]["challenger_minus_baseline"]["pooled_macro_f1"],
                    "worst_source_macro_f1_delta": stop["validation_confirmation_metrics"]["challenger_minus_baseline"]["worst_source_macro_f1"],
                    "bootstrap_95_percent": stop["validation_confirmation_metrics"]["paired_group_bootstrap"]["difference_percentile_95_ci"],
                },
            },
        ],
        "decision": {
            "bottleneck": "DATA_AND_SOURCE_ROBUSTNESS_BEFORE_MODEL_CAPACITY",
            "retain_current_frozen_baseline": True,
            "deploy_current_baseline": False,
            "train_an_agentic_or_large_generative_model_now": False,
            "next_hypothesis_family": "FROZEN_SEMANTIC_SENTENCE_EMBEDDINGS_PLUS_REGULARIZED_LINEAR_CLASSIFIER",
            "hypothesis": "A frozen semantic representation may reduce dependence on exact direct-address and marketing n-grams while retaining financial-activity meaning better than more lexical feature edits.",
            "first_stage_encoder_policy": "Encoder weights remain frozen; exact encoder, revision, license, checksum, pooling, truncation, and offline cache must be pinned in a separate protocol before any training.",
            "selection_data": "group_split_v2 train for fit and grouped development; validation for one confirmation only",
            "external_data_role": "V1/V2/V3 findings may motivate the hypothesis but their text, labels, predictions, and metrics may not select, tune, or reject the future candidate.",
            "required_gates": [
                "source-mean validation Macro-F1 improvement",
                "worst-source validation Macro-F1 non-degradation",
                "pooled validation Macro-F1 non-degradation",
                "source-predictability non-increase",
                "within-source shuffled-label diagnostic non-increase",
                "paired group-bootstrap lower bound above the predeclared margin",
            ],
            "external_evaluation_requirement": "Any selected candidate requires a new untouched evidence-backed external cohort; V2 and V3 must never be re-used for selection or headline evaluation.",
        },
        "not_selected_yet": {
            "exact_encoder": None,
            "embedding_dimension": None,
            "classifier_hyperparameters": None,
            "threshold": None,
            "reason": "Those choices require a separate pre-training protocol and dependency/license audit; this synthesis is not model selection.",
        },
        "safety_contract": {
            "model_fit_operations": 0,
            "model_scoring_operations": 0,
            "external_benchmark_transform_operations": 0,
            "threshold_changes": 0,
            "labels_changed": 0,
            "training_allowed": False,
            "deployment_allowed": False,
        },
        "next_gate": "Pin one exact frozen sentence-embedding encoder and predeclare the V4 development/validation protocol, dependencies, source-robustness gates, and failure actions before any embedding computation or classifier fit.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {args.output}")
    if sha256_file(args.config) != args.config_sha256:
        raise ValueError("Synthesis protocol hash mismatch")
    config = load_json(args.config)
    if config.get("protocol_id") != "ISI_TEXT_MODEL_DIRECTION_V4_EVIDENCE_SYNTHESIS":
        raise ValueError("Unexpected synthesis protocol")
    loaded = validate_inputs(config)
    output = build_synthesis(config, loaded)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": output["status"],
        "output": str(args.output),
        "sha256": sha256_file(args.output),
        "recurring_external_failure_profile": output["recurring_external_failure_profile"],
        "decision": output["decision"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
