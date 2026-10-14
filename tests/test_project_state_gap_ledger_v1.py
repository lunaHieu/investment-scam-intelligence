import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "project_state_gap_ledger_v1.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ProjectStateGapLedgerV1Tests(unittest.TestCase):
    def test_authority_statuses_reproduce_from_pinned_registries(self) -> None:
        ledger = json.loads(REGISTRY.read_text(encoding="utf-8"))
        role_to_status_key = {
            "mendeley_text_challenger_v4_oof_error_analysis": "mendeley_text",
            "external_text_intake_gate_v1": "external_text_intake",
            "external_text_ai_manual_adjudication_v1": "external_text_ai_review",
            "crimson_human_review_plan_v1": "crimson_review_plan",
            "crimson_human_review_decisions_v1": "crimson_decisions",
            "target_text_corpus_v1_core_release_contract_v1": "v1_core_release",
            "target_text_corpus_v1_group_split_contract_v1": "v1_core_split",
            "target_text_corpus_v1_train_materialization_contract_v1": "v1_core_train_materialization",
            "sec_edgar_iapd_wayback_availability_result_v3": "sec_iapd_wayback_v3",
            "sec_edgar_iapd_wayback_availability_retry_release_v4": "sec_iapd_wayback_v4",
            "mendeley_image_readiness_v1": "image_branch",
            "target_text_corpus_v1_source_capacity_amendment_protocol_v1": "source_capacity",
            "target_text_corpus_v1_vietnamese_channel_terms_v1": "vietnamese_channel",
        }
        self.assertEqual(set(role_to_status_key), {item["role"] for item in ledger["inputs"]})
        for item in ledger["inputs"]:
            source = json.loads((ROOT / item["path"]).read_text(encoding="utf-8"))
            self.assertEqual(source["status"], ledger["authority_statuses"][role_to_status_key[item["role"]]])

    def test_ledger_is_hash_bound_and_keeps_all_execution_gates_closed(self) -> None:
        ledger = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(len(ledger["inputs"]), 13)
        for item in ledger["inputs"] + ledger["implementation"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])

        findings = ledger["findings"]
        self.assertEqual(findings["mendeley_text"]["train_rows"], 3916)
        self.assertEqual(findings["external_text"]["ai_reviews_complete"], 21)
        self.assertEqual(findings["external_text"]["eligible_records"], 0)
        self.assertEqual(findings["crimson"]["planned_records"], 40)
        self.assertEqual(findings["crimson"]["first_reviews_recorded"], 1)
        self.assertEqual(findings["v1_core"]["required_groups"], 300)
        self.assertEqual(findings["v1_core"]["real_groups_validated"], 0)
        self.assertEqual(findings["sec_iapd_wayback"]["unresolved_rows"], 31)
        self.assertEqual(findings["image_branch"]["actual_image_assets"], 0)
        self.assertEqual(findings["vietnamese_channel"]["reference_records_acquired"], 0)

        self.assertEqual(
            [item["workstream_id"] for item in ledger["parallel_plan"]],
            ["P2_RAW_QA", "P3_EXTERNAL_21", "P4_CRIMSON_REVIEW", "P5_V1_CORE_GAPS", "P6_MANUAL_PACKETS", "P7_MODEL_DOSSIER", "P8_THESIS_DOCS"],
        )
        for gate in (
            "training_allowed",
            "validation_or_test_opening_allowed",
            "external_holdout_scoring_allowed",
            "image_training_allowed",
            "live_candidate_domain_access_allowed",
            "capture_before_complete_availability_qa_allowed",
            "automatic_label_conversion_allowed",
        ):
            self.assertFalse(ledger["decision"][gate])


if __name__ == "__main__":
    unittest.main()
