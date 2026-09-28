import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from src.isi.contracts import assert_feature_columns, assert_gold_is_untouched
from src.isi.collection.crimson import ingest_json
from src.isi.collection.mendeley import SOURCE_ID, ingest_csv
from src.isi.normalization.crimson import normalize_records


class ContractTests(unittest.TestCase):
    def test_safe_feature_columns_pass(self):
        assert_feature_columns({"text_embedding", "url_length", "ocr_token_count", "claim_roi"})

    def test_leakage_feature_is_rejected(self):
        with self.assertRaises(ValueError):
            assert_feature_columns({"text_embedding", "source_id"})

    def test_gold_cannot_be_used_for_tuning(self):
        with self.assertRaises(ValueError):
            assert_gold_is_untouched("gold", "select_threshold")

    def test_internal_test_remains_valid_for_evaluation(self):
        assert_gold_is_untouched("internal_test", "evaluate")

    def test_source_readiness_audit_exists(self):
        root = Path(__file__).resolve().parents[1]
        self.assertTrue((root / "registry" / "source_readiness.md").is_file())

    def test_crimson_url_feature_registry_keeps_training_gate_closed(self):
        root = Path(__file__).resolve().parents[1]
        registry = json.loads(
            (root / "registry" / "features" / "crimson_url_lexical_v1.json").read_text(encoding="utf-8")
        )
        self.assertEqual(registry["output_contract"]["label_fields"], [])
        self.assertEqual(registry["output_contract"]["network_operations"], 0)
        self.assertFalse(registry["training_gate"]["binary_classifier_allowed"])

    def test_financial_claim_registry_keeps_test_and_training_gates_closed(self):
        root = Path(__file__).resolve().parents[1]
        registry = json.loads(
            (root / "registry" / "features" / "mendeley_financial_claims_v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(registry["scope"]["test_partition_text_processed"], 0)
        self.assertFalse(registry["scope"]["source_labels_used_for_extraction"])
        self.assertEqual(registry["output_contract"]["label_fields"], [])
        self.assertFalse(registry["training_gate"]["binary_classifier_allowed"])

    def test_financial_claim_v2_registry_keeps_test_and_training_gates_closed(self):
        root = Path(__file__).resolve().parents[1]
        registry = json.loads(
            (root / "registry" / "features" / "mendeley_financial_claims_v2.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(registry["scope"]["test_partition_text_processed"], 0)
        self.assertFalse(registry["scope"]["source_labels_used_for_extraction"])
        self.assertFalse(registry["safety_contract"]["raw_files_modified"])
        self.assertFalse(registry["training_gate"]["binary_classifier_allowed"])

    def test_crimson_unsupervised_registry_is_exploratory_only(self):
        root = Path(__file__).resolve().parents[1]
        registry = json.loads(
            (root / "registry" / "analyses" / "crimson_domain_unsupervised_v1.json").read_text(encoding="utf-8")
        )
        safety = registry["safety_contract"]
        self.assertEqual(safety["network_operations"], 0)
        self.assertEqual(safety["labels_created"], 0)
        self.assertFalse(safety["training_allowed"])
        self.assertFalse(safety["domain_access_allowed"])
        self.assertNotEqual(registry["quality"]["stability_assessment"], "HIGH")

    def test_financial_claim_v2_review_records_ai_assisted_human_confirmation(self):
        root = Path(__file__).resolve().parents[1]
        registry = json.loads(
            (root / "registry" / "analyses" / "mendeley_financial_claims_review_workbook_v2.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(registry["source"]["test_partition_text_processed"], 0)
        self.assertEqual(registry["ai_assistance"]["human_decision_count"], 52)
        self.assertTrue(registry["ai_assistance"]["counts_as_human_review"])
        self.assertEqual(registry["human_confirmation"]["review_mode"], "AI_ASSISTED_HUMAN_CONFIRMATION")
        self.assertFalse(registry["human_confirmation"]["independent_blind_review"])
        self.assertFalse(registry["safety_contract"]["training_allowed"])

    def test_financial_claim_v3_registry_keeps_test_and_training_gates_closed(self):
        root = Path(__file__).resolve().parents[1]
        registry = json.loads(
            (root / "registry" / "features" / "mendeley_financial_claims_v3.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(registry["scope"]["test_partition_text_processed"], 0)
        self.assertFalse(registry["scope"]["source_labels_used_for_extraction"])
        self.assertFalse(registry["safety_contract"]["raw_files_modified"])
        self.assertFalse(registry["training_gate"]["binary_classifier_allowed"])

    def test_financial_claim_v3_review_records_ai_assisted_confirmation(self):
        root = Path(__file__).resolve().parents[1]
        registry = json.loads(
            (
                root
                / "registry"
                / "analyses"
                / "mendeley_financial_claims_review_workbook_v3.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(registry["source"]["test_partition_text_processed"], 0)
        self.assertEqual(registry["ai_assistance"]["suggestion_count"], 44)
        self.assertEqual(registry["ai_assistance"]["human_decision_count"], 44)
        self.assertTrue(registry["ai_assistance"]["counts_as_human_review"])
        self.assertTrue(registry["ai_assistance"]["changes_completion_status"])
        self.assertEqual(registry["human_confirmation"]["review_mode"], "AI_ASSISTED_HUMAN_CONFIRMATION")
        self.assertFalse(registry["human_confirmation"]["independent_blind_review"])
        self.assertFalse(registry["verification"]["human_input_columns_remain_blank"])
        self.assertFalse(registry["safety_contract"]["training_allowed"])

    def test_financial_claim_v4_registry_keeps_test_and_training_gates_closed(self):
        root = Path(__file__).resolve().parents[1]
        registry = json.loads(
            (root / "registry" / "features" / "mendeley_financial_claims_v4.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(registry["scope"]["test_partition_text_processed"], 0)
        self.assertFalse(registry["scope"]["source_labels_used_for_extraction"])
        self.assertFalse(registry["safety_contract"]["raw_files_modified"])
        self.assertEqual(registry["validation"]["filter_spot_check_status"], "VERIFIED")
        self.assertEqual(registry["validation"]["filter_spot_check_assignment_count"], 3)
        self.assertFalse(registry["training_gate"]["binary_classifier_allowed"])

    def test_financial_claim_v4_review_records_ai_assisted_confirmation(self):
        root = Path(__file__).resolve().parents[1]
        registry = json.loads(
            (
                root
                / "registry"
                / "analyses"
                / "mendeley_financial_claims_review_workbook_v4.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(registry["source"]["test_partition_text_processed"], 0)
        self.assertEqual(registry["ai_assistance"]["suggestion_count"], 37)
        self.assertEqual(registry["ai_assistance"]["human_decision_count"], 37)
        self.assertTrue(registry["ai_assistance"]["counts_as_human_review"])
        self.assertTrue(registry["ai_assistance"]["changes_completion_status"])
        self.assertEqual(registry["human_confirmation"]["review_mode"], "AI_ASSISTED_HUMAN_CONFIRMATION")
        self.assertFalse(registry["human_confirmation"]["independent_blind_review"])
        self.assertFalse(registry["verification"]["human_input_columns_remain_blank"])
        self.assertTrue(registry["verification"]["human_confirmation_package_validated"])
        self.assertFalse(registry["safety_contract"]["training_allowed"])
        self.assertEqual(registry["filter_spot_check"]["status"], "VERIFIED")
        self.assertEqual(registry["filter_spot_check"]["record_count"], 1)
        self.assertEqual(registry["filter_spot_check"]["false_positive_assignment_count"], 3)
        self.assertEqual(
            registry["training_gate"],
            "CLOSED_VALIDATION_ABLATION_COMPLETE_NO_PROMOTION",
        )

    def test_financial_claim_v4_group_split_v2_scope_and_training_gate(self):
        root = Path(__file__).resolve().parents[1]
        registry = json.loads(
            (
                root
                / "registry"
                / "features"
                / "mendeley_financial_claims_v4_group_split_v2.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(registry["source"]["split_version"], "group_split_v2")
        self.assertEqual(
            registry["scope"]["processed_partition_counts"],
            {"train": 3916, "validation": 838},
        )
        self.assertEqual(
            registry["scope"]["excluded_partition_counts"],
            {"test": 838, "auxiliary": 10607, "quarantine": 3},
        )
        self.assertEqual(registry["scope"]["test_partition_text_processed"], 0)
        self.assertEqual(registry["scope"]["auxiliary_rows_processed"], 0)
        self.assertEqual(registry["scope"]["quarantine_rows_processed"], 0)
        self.assertTrue(registry["validation"]["two_run_feature_hash_match"])
        self.assertTrue(registry["validation"]["full_deterministic_recomputation_passed"])
        self.assertFalse(registry["training_gate"]["binary_classifier_allowed"])
        self.assertFalse(registry["training_gate"]["validation_ablation_allowed"])
        self.assertFalse(registry["training_gate"]["test_evaluation_allowed"])

    def test_financial_claim_ablation_retains_text_only_without_opening_test(self):
        root = Path(__file__).resolve().parents[1]
        registry = json.loads(
            (
                root
                / "registry"
                / "models"
                / "mendeley_financial_claims_ablation_v1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            registry["status"],
            "FROZEN_VALIDATION_SELECTION_RETAIN_TEXT_ONLY_TEST_UNOPENED",
        )
        self.assertEqual(registry["decision"]["selected_variant"], "text_only")
        self.assertFalse(registry["decision"]["challenger_passes_all_promotion_gates"])
        self.assertFalse(registry["decision"]["open_internal_test_for_challenger"])
        self.assertEqual(registry["data_contract"]["test_rows_used"], 0)
        self.assertEqual(registry["data_contract"]["auxiliary_rows_used"], 0)
        self.assertEqual(registry["data_contract"]["quarantine_rows_used"], 0)
        self.assertFalse(registry["safety_contract"]["model_artifact_created"])
        self.assertFalse(registry["safety_contract"]["test_opened"])
        self.assertFalse(registry["safety_contract"]["deployment_allowed"])

    def test_mendeley_image_registry_keeps_image_training_blocked(self):
        root = Path(__file__).resolve().parents[1]
        registry = json.loads(
            (root / "registry" / "analyses" / "mendeley_image_readiness_v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(registry["status"], "FROZEN_BLOCKED_NO_IMAGE_ASSETS")
        self.assertFalse(registry["decision"]["has_usable_image_assets"])
        self.assertFalse(registry["decision"]["image_model_training_allowed"])
        self.assertEqual(registry["findings"]["actual_image_reference_count"], 0)

    def test_mendeley_text_baseline_v2_error_analysis_is_diagnostic_only(self):
        root = Path(__file__).resolve().parents[1]
        registry = json.loads(
            (
                root
                / "registry"
                / "analyses"
                / "mendeley_text_baseline_v2_error_analysis.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            registry["status"], "FROZEN_DIAGNOSTIC_ERROR_ANALYSIS_NO_TUNING"
        )
        self.assertFalse(registry["scope"]["model_fit_or_refit"])
        self.assertFalse(registry["scope"]["threshold_changed"])
        self.assertEqual(registry["scope"]["auxiliary_rows_used"], 0)
        self.assertEqual(registry["scope"]["quarantine_rows_used"], 0)
        self.assertEqual(registry["safety_contract"]["labels_created"], 0)
        self.assertFalse(registry["safety_contract"]["training_allowed"])
        self.assertFalse(registry["safety_contract"]["test_used_for_tuning"])

    def test_text_baseline_v2_external_readiness_blocks_invalid_scoring(self):
        root = Path(__file__).resolve().parents[1]
        registry = json.loads(
            (
                root
                / "registry"
                / "analyses"
                / "text_baseline_v2_external_readiness_v1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            registry["status"], "FROZEN_BLOCKED_NO_ELIGIBLE_EXTERNAL_TEXT_CASES"
        )
        self.assertEqual(registry["findings"]["eligible_external_text_records"], 0)
        self.assertFalse(registry["findings"]["external_reporting_allowed"])
        self.assertFalse(registry["decision"]["external_text_scoring_performed"])
        self.assertEqual(registry["safety_contract"]["model_scoring_operations"], 0)
        self.assertEqual(registry["safety_contract"]["labels_created"], 0)
        self.assertFalse(registry["safety_contract"]["training_allowed"])

    def test_external_text_intake_gate_stays_blocked_without_reconciled_records(self):
        root = Path(__file__).resolve().parents[1]
        registry = json.loads(
            (
                root
                / "registry"
                / "analyses"
                / "external_text_intake_gate_v1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            registry["status"],
            "TWENTY_ONE_DRAFTS_IN_REVIEW_BLOCKED_ZERO_ELIGIBLE_RECORDS",
        )
        self.assertEqual(registry["raw_inventory"]["sec_iapd_files"], 1)
        self.assertEqual(registry["raw_inventory"]["iosco_i_scan_files"], 1)
        self.assertEqual(
            registry["raw_inventory"]["external_text_capture_candidate_count"], 30
        )
        self.assertEqual(
            registry["raw_inventory"]["external_text_reserve_candidate_count"], 30
        )
        self.assertEqual(registry["raw_inventory"]["external_text_capture_files"], 33)
        self.assertEqual(registry["raw_inventory"]["external_warning_evidence_files"], 12)
        self.assertEqual(registry["raw_inventory"]["external_text_draft_records"], 21)
        self.assertEqual(
            registry["raw_inventory"]["external_text_confirmed_draft_records"], 10
        )
        self.assertEqual(
            registry["raw_inventory"]["external_text_legitimate_draft_records"], 11
        )
        self.assertEqual(registry["raw_inventory"]["external_text_eligible_records"], 0)
        self.assertEqual(registry["template_validation"]["structural_error_count"], 0)
        self.assertEqual(registry["template_validation"]["eligible_records"], 0)
        self.assertFalse(registry["template_validation"]["reporting_allowed"])
        self.assertFalse(registry["decision"]["external_text_scoring_performed"])
        self.assertFalse(registry["decision"]["external_metrics_reported"])
        self.assertFalse(registry["safety_contract"]["domain_access_allowed"])
        self.assertFalse(registry["safety_contract"]["training_allowed"])

    def test_mendeley_metadata_ablation_does_not_promote_source_shortcuts(self):
        root = Path(__file__).resolve().parents[1]
        registry = json.loads(
            (root / "registry" / "models" / "mendeley_metadata_ablation_v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertFalse(registry["feature_safety"]["source_dataset_used_as_predictive_feature"])
        self.assertFalse(
            registry["selection_policy"]["test_used_for_hyperparameter_or_variant_selection"]
        )
        self.assertGreater(
            registry["source_confounding_diagnostics"][
                "test_missingness_to_source_macro_f1"
            ],
            0.5,
        )
        self.assertFalse(registry["decision"]["promote_metadata_to_primary_baseline"])
        self.assertFalse(registry["decision"]["deployment_allowed"])

    def test_mendeley_source_balance_ablation_keeps_source_out_of_features(self):
        root = Path(__file__).resolve().parents[1]
        registry = json.loads(
            (root / "registry" / "models" / "mendeley_source_balance_ablation_v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertFalse(registry["model_contract"]["source_dataset_in_feature_matrix"])
        self.assertFalse(registry["selection_policy"]["test_used_for_strategy_selection"])
        self.assertEqual(
            registry["selection_policy"]["selected_strategy_on_validation"], "unweighted"
        )
        self.assertFalse(registry["decision"]["promote_to_primary_internal_baseline"])
        self.assertFalse(registry["decision"]["deployment_allowed"])

    def test_mendeley_text_representation_ablation_blocks_shortcut_promotion(self):
        root = Path(__file__).resolve().parents[1]
        registry = json.loads(
            (
                root
                / "registry"
                / "models"
                / "mendeley_text_representation_ablation_v1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertFalse(registry["representation_contract"]["source_dataset_in_feature_matrix"])
        self.assertFalse(
            registry["selection_policy"][
                "test_used_for_hyperparameter_or_representation_selection"
            ]
        )
        self.assertNotIn(
            "char_3_5", registry["selection_policy"]["promotion_eligible_representations"]
        )
        self.assertGreater(
            registry["data_contract"]["normalized_template_partition_audit"][
                "cross_partition_template_count"
            ],
            0,
        )
        self.assertFalse(registry["decision"]["qualifies_as_internal_research_candidate"])
        self.assertFalse(registry["decision"]["promote_to_primary_internal_baseline"])
        self.assertFalse(registry["decision"]["deployment_allowed"])

    def test_mendeley_group_split_v2_keeps_auxiliary_and_quarantine_out(self):
        root = Path(__file__).resolve().parents[1]
        registry = json.loads(
            (root / "registry" / "splits" / "mendeley_group_split_v2.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(registry["status"], "FROZEN_DERIVED_SPLIT")
        self.assertEqual(
            registry["routing_contract"]["partition_counts"],
            {
                "train": 3916,
                "validation": 838,
                "test": 838,
                "auxiliary": 10607,
                "quarantine": 3,
            },
        )
        self.assertEqual(
            registry["grouping_contract"]["component_cross_partition_count"], 0
        )
        self.assertFalse(
            registry["usage_policy"]["auxiliary_allowed_in_benchmark_training_or_scoring"]
        )
        self.assertFalse(
            registry["usage_policy"]["quarantine_allowed_in_benchmark_training_or_scoring"]
        )
        self.assertFalse(registry["usage_policy"]["external_or_gold_test"])
        self.assertFalse(registry["safety_contract"]["model_training_performed"])
        self.assertEqual(registry["safety_contract"]["source_labels_changed"], 0)

    def test_mendeley_text_baseline_v2_freezes_selection_before_test(self):
        root = Path(__file__).resolve().parents[1]
        registry = json.loads(
            (root / "registry" / "models" / "text_baseline_v2.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(registry["data_contract"]["split_version"], "group_split_v2")
        self.assertEqual(registry["data_contract"]["auxiliary_rows_used"], 0)
        self.assertEqual(registry["data_contract"]["quarantine_rows_used"], 0)
        self.assertEqual(
            registry["selection_policy"]["test_text_transformed_during_selection"], 0
        )
        self.assertEqual(
            registry["selection_policy"]["test_labels_used_during_selection"], 0
        )
        self.assertFalse(registry["selection_policy"]["test_used_for_selection"])
        self.assertTrue(
            registry["selection_policy"]["test_opened_after_selection_frozen"]
        )
        self.assertEqual(registry["primary_model"]["predictive_input"], ["text_content"])
        self.assertFalse(registry["safety_contract"]["deployment_allowed"])

    def test_mendeley_ingest_creates_immutable_raw_manifest_and_profile(self):
        workspace_root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory(dir=workspace_root) as temp_dir:
            root = Path(temp_dir)
            source = root / "source.csv"
            source.write_text("record_id,text,label\n1,hello,0\n2,,1\n", encoding="utf-8")
            raw, manifest, report = ingest_csv(source, root / "raw", root / "manifests", root / "reports")
            self.assertTrue(raw.is_file())
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["source_id"], SOURCE_ID)
            profile = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(profile["row_count"], 2)
            self.assertEqual(profile["missing_value_count_by_column"]["text"], 1)

    def test_crimson_ingest_creates_pinned_raw_manifest_and_profile(self):
        workspace_root = Path(__file__).resolve().parents[1]
        commit = "b040e2def08ea26058ef9da752b72fa4a5238987"
        with TemporaryDirectory(dir=workspace_root) as temp_dir:
            root = Path(temp_dir)
            source = root / "data.json"
            source.write_text('[{"url":"https://example.test","label":"scam"}]', encoding="utf-8")
            raw, manifest, report = ingest_json(
                source, root / "raw", root / "manifests", root / "reports", commit
            )
            self.assertTrue(raw.is_file())
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["source_version"], commit)
            profile = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(profile["row_count"], 1)
            self.assertEqual(profile["field_presence_count"]["url"], 1)

    def test_crimson_normalization_never_fetches_urls_and_reports_invalid_values(self):
        workspace_root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory(dir=workspace_root) as temp_dir:
            root = Path(temp_dir)
            source = root / "data.json"
            source.write_text(
                '[{"url":"Example.test"},{"url":"https://Example.test/path"},{"url":"not-a-url"}]', encoding="utf-8"
            )
            output = root / "candidates.jsonl"
            report = normalize_records(source, output, __import__("datetime").date(2026, 9, 8))
            self.assertEqual(report["candidate_artifact_count"], 2)
            self.assertEqual(report["invalid_url_count"], 1)
            self.assertEqual(report["bare_domain_canonicalized_count"], 1)
            artifact = json.loads(output.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(artifact["domain"], "example.test")
            self.assertEqual(artifact["url"], "https://Example.test")
            self.assertEqual(artifact["artifact_type"], "URL")


if __name__ == "__main__":
    unittest.main()
