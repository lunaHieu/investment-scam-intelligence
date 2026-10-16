import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "registry" / "analyses" / "data_sufficiency_audit_v1.json"


class DataSufficiencyAuditV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = json.loads(AUDIT.read_text(encoding="utf-8"))

    def test_all_pinned_repository_inputs_and_implementation_are_current(self) -> None:
        for item in self.data["inputs"] + self.data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                item["sha256"],
                item["path"],
            )

    def test_counts_are_separated_by_semantic_role(self) -> None:
        findings = self.data["findings"]
        self.assertEqual(findings["raw_storage"]["file_count"], 278)
        self.assertEqual(findings["raw_storage"]["verified_file_count"], 278)
        self.assertEqual(findings["raw_storage"]["byte_count"], 1_640_058_635)

        benchmark = findings["historical_benchmark"]
        self.assertEqual(benchmark["raw_rows"], 16_202)
        self.assertEqual(benchmark["benchmark_eligible_rows"], 5_592)
        self.assertEqual(benchmark["train_rows"], 3_916)
        self.assertEqual(benchmark["validation_rows"], 838)
        self.assertEqual(benchmark["test_rows"], 838)
        self.assertEqual(benchmark["train_groups"], 3_783)
        self.assertEqual(benchmark["auxiliary_rows"], 10_607)
        self.assertEqual(benchmark["quarantine_rows"], 3)

        reference = findings["reference_metadata"]
        self.assertEqual(reference["sec_edgar_all_filer_entries"], 988_519)
        self.assertEqual(reference["iosco_warning_entries"], 47_001)
        self.assertEqual(reference["iapd_entries"], 23_927)
        self.assertFalse(reference["count_as_training_rows"])

        target = findings["fresh_target_corpus"]
        self.assertEqual(target["required_groups"], 300)
        self.assertEqual(target["development_groups_required"], 240)
        self.assertEqual(target["external_holdout_groups_required"], 60)
        self.assertEqual(target["validated_release_groups"], 0)
        self.assertEqual(target["completion_percent"], 0.0)
        self.assertEqual(target["diagnostic_decisive_target_text_pilot_rows"], 15)
        self.assertEqual(target["training_eligible_rows"], 0)

        pipeline = findings["acquisition_pipeline"]
        self.assertEqual(pipeline["sec_iapd_candidates"], 115)
        self.assertEqual(pipeline["sec_iapd_resolved"], 92)
        self.assertEqual(pipeline["sec_iapd_available"], 45)
        self.assertEqual(pipeline["sec_iapd_unavailable"], 47)
        self.assertEqual(pipeline["sec_iapd_unresolved"], 23)
        self.assertEqual(pipeline["sec_iapd_training_ready_rows"], 0)

    def test_key_counts_recompute_from_pinned_source_registries(self) -> None:
        load = lambda relative: json.loads((ROOT / relative).read_text(encoding="utf-8"))
        findings = self.data["findings"]

        raw = load("registry/analyses/raw_cross_registry_provenance_audit_v2.json")["findings"]
        self.assertEqual(findings["raw_storage"]["file_count"], raw["raw_file_count"])
        self.assertEqual(findings["raw_storage"]["byte_count"], raw["raw_byte_count"])

        split = load("registry/splits/mendeley_group_split_v2.json")
        benchmark = findings["historical_benchmark"]
        self.assertEqual(benchmark["raw_rows"], split["source"]["raw_row_count"])
        self.assertEqual(benchmark["benchmark_eligible_rows"], split["routing_contract"]["benchmark_eligible_rows"])
        for partition in ("train", "validation", "test", "auxiliary"):
            self.assertEqual(benchmark[f"{partition}_rows"], split["routing_contract"]["partition_counts"][partition])
        self.assertEqual(benchmark["quarantine_rows"], split["routing_contract"]["partition_counts"]["quarantine"])
        self.assertEqual(benchmark["train_groups"], split["split_quality"]["group_count_by_partition"]["train"])

        target_contract = load("registry/analyses/target_text_corpus_v1_core_release_contract_v1.json")["findings"]
        target = findings["fresh_target_corpus"]
        self.assertEqual(target["required_groups"], target_contract["required_total_groups"])
        self.assertEqual(target["validated_release_groups"], target_contract["real_records_validated"])

        pilot = load("registry/analyses/target_text_corpus_v1_owner_acceptance_result_v1.json")["findings"]
        self.assertEqual(target["target_text_pilot_reviewed_rows"], pilot["reviewed_records"])
        self.assertEqual(target["diagnostic_decisive_target_text_pilot_rows"], pilot["decisive_labels_materialized"])
        self.assertEqual(target["training_eligible_rows"], pilot["training_eligible_records"])

        ledger = load("registry/analyses/project_state_gap_ledger_v5.json")["state_amendments"]["P1_SEC_IAPD"]
        pipeline = findings["acquisition_pipeline"]
        for key, source_key in (
            ("sec_iapd_candidates", "planned"),
            ("sec_iapd_resolved", "resolved"),
            ("sec_iapd_available", "available"),
            ("sec_iapd_unavailable", "unavailable"),
            ("sec_iapd_unresolved", "unresolved"),
        ):
            self.assertEqual(pipeline[key], ledger[source_key])

        references = findings["reference_metadata"]
        reference_sources = (
            ("sec_edgar_all_filer_entries", "registry/analyses/sec_edgar_all_filer_identity_index_v1.json"),
            ("iosco_warning_entries", "registry/analyses/iosco_warning_reference_index_v1.json"),
            ("iapd_entries", "registry/analyses/sec_iapd_reference_index_v1.json"),
        )
        for key, relative in reference_sources:
            source = load(relative)
            count = source.get("findings", {}).get("indexed_records")
            if count is None:
                count = source["input"]["record_count"]
            self.assertEqual(references[key], count)

    def test_conclusions_and_safety_gates_remain_closed(self) -> None:
        decision = self.data["decision"]
        self.assertTrue(decision["existing_raw_integrity_complete"])
        self.assertFalse(decision["total_planned_raw_acquisition_complete"])
        self.assertTrue(decision["baseline_internal_training_data_exists"])
        self.assertFalse(decision["fresh_target_training_ready"])
        self.assertFalse(decision["model_promotion_allowed"])
        self.assertFalse(decision["validation_or_test_opening_allowed"])
        self.assertFalse(decision["candidate_or_reference_counts_are_training_rows"])

        safety = self.data["safety_contract"]
        self.assertEqual(safety["network_operations"], 0)
        self.assertEqual(safety["labels_created"], 0)
        self.assertEqual(safety["model_operations"], 0)
        self.assertEqual(safety["validation_or_test_openings"], 0)
        self.assertFalse(safety["training_allowed"])


if __name__ == "__main__":
    unittest.main()
