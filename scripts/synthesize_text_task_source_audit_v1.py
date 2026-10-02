"""Synthesize the frozen no-training audit of text-task and source alignment."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "configs" / "text_task_source_audit_v1_protocol.json"
EXPECTED_PROTOCOL_SHA256 = (
    "45949f060f7a7d1c6203093db8ac77594b99c0e09658aa3854c10af2c2c7d2cf"
)
ANALYSIS_ID = "ISI_TEXT_TASK_SOURCE_AUDIT_V1"
STATUS = "FROZEN_SOURCE_ROLE_AUDIT_COMPLETE_NO_CORPUS_OR_MODEL_CHANGE"


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


def verify_protocol() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    actual_protocol_hash = sha256_file(PROTOCOL_PATH)
    if actual_protocol_hash != EXPECTED_PROTOCOL_SHA256:
        raise ValueError(
            "Protocol changed after freeze: "
            f"expected {EXPECTED_PROTOCOL_SHA256}, found {actual_protocol_hash}"
        )
    protocol = load_json(PROTOCOL_PATH)
    inputs: dict[str, dict[str, Any]] = {}
    for item in protocol["inputs"]:
        path = ROOT / item["path"]
        actual_hash = sha256_file(path)
        if actual_hash != item["sha256"]:
            raise ValueError(f"Pinned input changed: {item['role']}")
        inputs[item["role"]] = load_json(path)
    return protocol, inputs


def source_role_recommendations() -> dict[str, dict[str, Any]]:
    return {
        "cresci_stock_2018": {
            "observed_source_family": "finance-related social-media records",
            "target_alignment": "INDIRECT_RELATED_DECEPTION_NOT_VERIFIED_SCAM",
            "text_only_identifiability": "PARTIAL",
            "recommended_role": "RELATED_CONTENT_AUXILIARY_RESEARCH",
            "retain_in_existing_group_split_v2_benchmark": True,
            "use_as_final_target_domain_ground_truth": False,
        },
        "phishing": {
            "observed_source_family": "phishing text",
            "target_alignment": "RELATED_MESSAGE_ABUSE_NOT_INVESTMENT_SCAM_IDENTITY",
            "text_only_identifiability": "PARTIAL_TO_HIGH_WITH_TEMPLATE_RISK",
            "recommended_role": "RELATED_CONTENT_AUXILIARY_RESEARCH",
            "retain_in_existing_group_split_v2_benchmark": True,
            "use_as_final_target_domain_ground_truth": False,
        },
        "spam_email": {
            "observed_source_family": "spam email",
            "target_alignment": "RELATED_UNSOLICITED_CONTENT_NOT_VERIFIED_SCAM",
            "text_only_identifiability": "HIGH_IN_SOURCE_LOW_TRANSFER_CERTAINTY",
            "recommended_role": "RELATED_CONTENT_AUXILIARY_RESEARCH",
            "retain_in_existing_group_split_v2_benchmark": True,
            "use_as_final_target_domain_ground_truth": False,
        },
        "twitter_bot_detection": {
            "observed_source_family": "Twitter bot-detection records",
            "target_alignment": "ACCOUNT_AUTOMATION_NOT_CONTENT_SCAM_STATUS",
            "text_only_identifiability": "LOW",
            "recommended_role": "ACCOUNT_OR_BEHAVIOR_AUXILIARY_TASK",
            "retain_in_existing_group_split_v2_benchmark": True,
            "use_as_final_target_domain_ground_truth": False,
        },
        "fake_profile_post": {
            "observed_source_family": "fake-profile posts",
            "target_alignment": "PROFILE_AUTHENTICITY_NOT_CONTENT_SCAM_STATUS",
            "text_only_identifiability": "TEMPLATE_DOMINATED_AND_NOT_INDEPENDENTLY_SPLITTABLE",
            "recommended_role": "ACCOUNT_OR_BEHAVIOR_AUXILIARY_TASK",
            "retain_in_existing_group_split_v2_benchmark": False,
            "use_as_final_target_domain_ground_truth": False,
        },
        "conflicting_phishing_component": {
            "observed_source_family": "duplicate phishing component with conflicting labels",
            "target_alignment": "UNRESOLVED",
            "text_only_identifiability": "NOT_APPLICABLE",
            "recommended_role": "QUARANTINE",
            "retain_in_existing_group_split_v2_benchmark": False,
            "use_as_final_target_domain_ground_truth": False,
        },
    }


def build_result(protocol: dict[str, Any], inputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    split = inputs["group_split_registry"]
    baseline = inputs["baseline_registry"]
    baseline_error = inputs["baseline_error_registry"]
    metadata = inputs["metadata_ablation_registry"]
    semantic = inputs["semantic_challenger_registry"]
    semantic_error = inputs["semantic_error_registry"]
    wayback_v2 = inputs["wayback_language_error_registry"]
    wayback_v3 = inputs["wayback_holdout_error_registry"]

    return {
        "analysis_id": ANALYSIS_ID,
        "run_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": STATUS,
        "protocol": {
            "path": str(PROTOCOL_PATH.relative_to(ROOT)).replace("/", "\\"),
            "sha256": EXPECTED_PROTOCOL_SHA256,
        },
        "inputs": [
            {
                "role": item["role"],
                "path": item["path"],
                "sha256": item["sha256"],
            }
            for item in protocol["inputs"]
        ],
        "published_scope": protocol["official_source_statement"],
        "dataset_contract": {
            "label_semantics": split["label_semantics"],
            "raw_rows": split["source"]["raw_row_count"],
            "benchmark_rows": split["routing_contract"]["benchmark_eligible_rows"],
            "train_rows": split["routing_contract"]["partition_counts"]["train"],
            "validation_rows": split["routing_contract"]["partition_counts"]["validation"],
            "test_rows": split["routing_contract"]["partition_counts"]["test"],
            "auxiliary_rows": split["routing_contract"]["partition_counts"]["auxiliary"],
            "quarantine_rows": split["routing_contract"]["partition_counts"]["quarantine"],
            "benchmark_sources": split["routing_contract"]["benchmark_sources"],
        },
        "existing_evidence": {
            "baseline_test": {
                "pooled_macro_f1": baseline["metrics"]["test"]["macro_f1"],
                "per_source_macro_f1": baseline["metrics"][
                    "test_macro_f1_by_source_dataset"
                ],
                "worst_source": baseline["metrics"]["test_source_summary"][
                    "worst_source_dataset"
                ],
                "worst_source_macro_f1": baseline["metrics"]["test_source_summary"][
                    "worst_source_macro_f1"
                ],
            },
            "baseline_error_concentration": {
                "all_errors": baseline_error["findings"]["error_rows"],
                "twitter_errors": baseline_error["findings"]["twitter_error_rows"],
                "twitter_share_of_errors": baseline_error["findings"][
                    "twitter_share_of_all_errors"
                ],
                "short_errors_lte_12_tokens": baseline_error["findings"][
                    "short_error_rows_lte_12_surface_tokens"
                ],
            },
            "source_shortcut_diagnostics": {
                "metadata_missingness_test_source_accuracy": metadata[
                    "source_confounding_diagnostics"
                ]["test_missingness_to_source_accuracy"],
                "source_majority_label_test_accuracy": metadata[
                    "source_confounding_diagnostics"
                ]["test_source_majority_label_accuracy"],
                "frozen_e5_source_predictability_macro_f1": semantic["metrics"][
                    "challenger"
                ]["source_predictability_macro_f1"],
                "frozen_e5_nearest_neighbor_same_source_rate": semantic_error[
                    "findings"
                ]["headline"]["nearest_neighbor_same_source_rate"],
                "frozen_e5_net_regression_rate": semantic_error["findings"][
                    "headline"
                ]["net_e5_regression_rate"],
            },
            "external_transfer_diagnostics": {
                "wayback_v2_records": wayback_v2["findings"]["record_count"],
                "wayback_v2_errors": wayback_v2["findings"]["error_count"],
                "wayback_v2_nearest_spam_email": wayback_v2["findings"][
                    "nearest_fit_spam_email_count_all_records"
                ],
                "wayback_v3_records": wayback_v3["findings"]["record_count"],
                "wayback_v3_errors": wayback_v3["findings"]["error_count"],
                "wayback_v3_nearest_spam_email": wayback_v3["findings"][
                    "nearest_fit_spam_email_count_all_records"
                ],
            },
            "challenger_statuses": {
                "character_v2": inputs["character_challenger_registry"]["status"],
                "stopword_v3": inputs["stopword_challenger_registry"]["status"],
                "semantic_v4": semantic["status"],
            },
        },
        "source_role_recommendations": source_role_recommendations(),
        "decision": {
            "primary_task_misalignment_found": True,
            "mendeley_group_split_v2_role": "HISTORICAL_HETEROGENEOUS_BENCHMARK",
            "mendeley_source_label_is_final_investment_scam_ground_truth": False,
            "remove_or_relabel_existing_rows_now": False,
            "retain_text_baseline_v2_as_historical_reference": True,
            "deploy_text_baseline_v2": False,
            "train_another_model_now": False,
            "new_model_or_corpus_configuration_authorized": False,
            "recommended_primary_target": "EVIDENCE_BACKED_INVESTMENT_SOLICITATION_OR_WEBSITE_RISK_WITH_CASE_LEVEL_CONFIRMED_OR_LEGITIMATE STATUS",
            "next_required_artifact": "A separate owner-visible target-task and corpus-construction protocol for new development data; existing opened external cohorts remain diagnostic-only and cannot be reused for model selection.",
        },
        "interpretation": {
            "supported": [
                "The pooled binary label combines heterogeneous deception, spam, phishing, profile authenticity, and bot-detection tasks after investment filtering.",
                "Investment relevance filtering does not convert the harmonized source label into verified investment-scam ground truth.",
                "The existing text model is highly source-dependent and transfers imperfectly to evidence-backed website cases.",
                "Twitter bot labels are poorly identifiable from short text alone and should be treated as a separate account-or-behavior auxiliary task in future work."
            ],
            "not_supported": [
                "Any individual Mendeley row is mislabeled.",
                "Removing Twitter rows would necessarily improve real-world investment-scam detection.",
                "One particular encoder, chunking method, or hyperparameter will solve the task mismatch.",
                "Opened external benchmarks may be converted into tuning data."
            ],
        },
        "safety_contract": {
            "network_research_operations_after_protocol_freeze": 0,
            "new_row_level_data_access": 0,
            "model_fit_operations": 0,
            "model_scoring_operations": 0,
            "labels_changed": 0,
            "split_changes": 0,
            "training_eligibility_changes": 0,
            "validation_or_test_openings": 0,
            "training_allowed": False,
            "deployment_allowed": False,
        },
    }


def write_json_once(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    protocol, inputs = verify_protocol()
    result = build_result(protocol, inputs)
    write_json_once(args.output, result)
    print(json.dumps({
        "analysis_id": ANALYSIS_ID,
        "status": STATUS,
        "output": str(args.output),
        "source_role_count": len(result["source_role_recommendations"]),
        "model_fit_operations": 0,
        "validation_or_test_openings": 0,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

