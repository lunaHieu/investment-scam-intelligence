import unittest

from src.isi.curation.legitimate_reconciliation_review import (
    assess_legitimate_reconciliation_record,
)


def record(text: str) -> dict:
    return {
        "case_id": "CASE_LEGIT_TEST",
        "ground_truth_status": "UNCERTAIN",
        "label_confidence": "LOW",
        "review_status": "IN_REVIEW",
        "artifact": {
            "source_record_id": "123",
            "content_observed_at": "2026-09-24",
            "text": text,
            "text_sha256": "a" * 64,
            "source_capture_path": "capture.html",
            "source_capture_sha256": "b" * 64,
        },
        "evidence": [{"reviewed": False}],
    }


def first_pass() -> dict:
    return {
        "sec_profile": {
            "crd": "123",
            "sec_number": "801-123",
            "business_name": "Example Capital",
            "legal_name": "Example Capital LLC",
            "registration": {"FirmType": "Registered", "St": "APPROVED"},
            "filing": {"Dt": "2026-09-01"},
            "normalized_web_hosts": ["example.test"],
        },
        "comparison": {
            "artifact_host": "example.test",
            "host_exactly_listed_in_sec_filing": True,
            "registered_and_approved": True,
            "identity_token_check": {"any_full_token_match": True},
            "contact_field_check": {"matched_count": 3, "available_count": 5},
        },
        "ai_first_pass": {
            "recommended_identity_relationship": "SAME_ENTITY_LIKELY",
            "recommended_evidence_assessment": "REGISTRATION_RELEVANT",
            "recommended_outcome_for_human_review": "LEGITIMATE",
            "recommendation_confidence": "HIGH",
        },
    }


class LegitimateReconciliationReviewTests(unittest.TestCase):
    def test_all_gates_pass_without_creating_label(self):
        text = "Example Capital provides long-term investment planning. " * 12
        result = assess_legitimate_reconciliation_record(
            record(text), first_pass(), raw_capture_hash_valid=True, text_hash_valid=True
        )
        self.assertTrue(result["automated_second_pass"]["all_automatic_gates_pass"])
        self.assertEqual(
            result["automated_second_pass"]["proposed_outcome_for_human_review"],
            "LEGITIMATE",
        )
        self.assertFalse(result["automated_second_pass"]["recommendation_is_ground_truth"])
        self.assertIsNone(result["human_decision"]["decision"])
        self.assertFalse(result["external_evaluation_eligible"])

    def test_host_mismatch_blocks_legitimate_proposal(self):
        report = first_pass()
        report["comparison"]["host_exactly_listed_in_sec_filing"] = False
        result = assess_legitimate_reconciliation_record(
            record("Example Capital investment planning. " * 12),
            report,
            raw_capture_hash_valid=True,
            text_hash_valid=True,
        )
        self.assertIn(
            "captured_host_exactly_listed_in_sec_filing",
            result["contradiction_review"]["hard_contradictions"],
        )
        self.assertEqual(
            result["automated_second_pass"]["proposed_outcome_for_human_review"],
            "UNCERTAIN",
        )

    def test_contact_absence_and_short_text_are_cautions_only(self):
        report = first_pass()
        report["comparison"]["contact_field_check"] = {
            "matched_count": 0,
            "available_count": 5,
        }
        text = "Example Capital investment planning and portfolio services. " * 5
        result = assess_legitimate_reconciliation_record(
            record(text), report, raw_capture_hash_valid=True, text_hash_valid=True
        )
        cautions = result["contradiction_review"]["caution_flags"]
        self.assertIn("NO_SEC_CONTACT_FIELD_MATCH_IN_CAPTURE", cautions)
        self.assertIn("SHORT_PRESERVED_VISIBLE_TEXT_UNDER_500_CHARACTERS", cautions)
        self.assertEqual(result["contradiction_review"]["hard_contradictions"], [])
        self.assertEqual(
            result["automated_second_pass"]["recommendation_confidence"],
            "MEDIUM_HIGH_FOR_HUMAN_REVIEW",
        )


if __name__ == "__main__":
    unittest.main()
