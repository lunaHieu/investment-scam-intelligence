import unittest

from src.isi.curation.confirmed_text_review import assess_confirmed_record


def record():
    return {
        "case_id": "CASE_CONF_001",
        "artifact": {
            "text": "Example Capital investment trading market wealth " * 20,
            "text_sha256": "a" * 64,
            "url": "https://web.archive.org/web/20260611222510id_/https://example.test/",
            "source_capture_path": "external/capture.html",
            "source_capture_sha256": "b" * 64,
        },
    }


def candidate():
    return {
        "candidate_id": "EXTCAP_CONF_001",
        "candidate_host": "example.test",
        "entity_name_keys": ["Example Capital"],
        "source_id": "iosco_i_scan",
        "official_reference": {
            "url": "https://regulator.example/warning",
            "regulator": {"name": "Regulator", "jurisdiction": "Test"},
            "warning_categories": {"category": "1"},
            "evidence_dates": {"validation_date": "2026-09-21"},
        },
    }


class ConfirmedTextReviewTests(unittest.TestCase):
    def test_archive_and_local_warning_alignment_is_high_confidence_recommendation(self):
        screen = {
            "candidate_host_in_visible_text": True,
            "identity_check": {"any_full_token_match": True},
        }
        result = assess_confirmed_record(record(), candidate(), screen)
        self.assertTrue(result["archive_snapshot"]["candidate_host_match"])
        self.assertTrue(result["comparison"]["archive_snapshot_not_after_warning"])
        self.assertEqual(
            result["ai_first_pass"]["recommended_outcome_for_human_review"], "CONFIRMED"
        )
        self.assertEqual(result["ai_first_pass"]["recommendation_confidence"], "HIGH")
        self.assertFalse(result["ai_first_pass"]["recommendation_is_ground_truth"])
        self.assertFalse(result["external_evaluation_eligible"])

    def test_missing_local_warning_capture_reduces_recommendation_confidence(self):
        result = assess_confirmed_record(record(), candidate(), None)
        self.assertEqual(result["ai_first_pass"]["recommendation_confidence"], "MEDIUM_HIGH")
        self.assertFalse(result["official_warning"]["local_capture_available"])

    def test_identity_mismatch_remains_uncertain(self):
        item = record()
        item["artifact"]["text"] = "Unrelated software consulting content. " * 20
        result = assess_confirmed_record(item, candidate(), None)
        self.assertEqual(
            result["ai_first_pass"]["recommended_outcome_for_human_review"], "UNCERTAIN"
        )
        self.assertEqual(result["ai_first_pass"]["recommendation_confidence"], "LOW")


if __name__ == "__main__":
    unittest.main()
