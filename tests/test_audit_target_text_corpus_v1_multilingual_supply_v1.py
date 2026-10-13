import unittest

from scripts.audit_target_text_corpus_v1_multilingual_supply_v1 import reviewed_language, select_population


CONTRACT = {
    "required_visible_text_field": "observed_artifact_visible_text",
    "required_text_sha256_field": "observed_artifact_text_sha256",
    "required_human_review_field": "human_reviewed_language",
    "allowed_reviewed_languages": ["ENGLISH", "VIETNAMESE", "OTHER_NON_ENGLISH"],
}


class AuditTargetTextCorpusV1MultilingualSupplyV1Tests(unittest.TestCase):
    def test_reference_metadata_without_text_routes_to_unknown(self) -> None:
        self.assertEqual(reviewed_language({"candidate_url": "https://example.test/"}, CONTRACT), "UNKNOWN")

    def test_domain_or_name_does_not_create_vietnamese_decision(self) -> None:
        row = {"candidate_url": "https://example.vn/", "entity_country": "Vietnam"}
        self.assertEqual(reviewed_language(row, CONTRACT), "UNKNOWN")

    def test_complete_reviewed_text_can_supply_language(self) -> None:
        row = {"observed_artifact_visible_text": "Nội dung đầu tư", "observed_artifact_text_sha256": "a" * 64, "human_reviewed_language": "VIETNAMESE"}
        self.assertEqual(reviewed_language(row, CONTRACT), "VIETNAMESE")

    def test_population_filter_is_exact(self) -> None:
        rows = [{"decision": "ADVANCE"}, {"decision": "HOLD"}]
        self.assertEqual(select_population(rows, {"field": "decision", "equals": "ADVANCE", "expected_rows": 1}), [rows[0]])


if __name__ == "__main__":
    unittest.main()
