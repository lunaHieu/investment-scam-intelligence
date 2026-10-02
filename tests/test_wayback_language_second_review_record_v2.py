import unittest

from scripts.record_wayback_language_second_review_v2 import REVIEW_TYPE, validate_reviews


class WaybackLanguageSecondReviewRecordV2Tests(unittest.TestCase):
    def test_validates_exact_blind_coverage(self):
        packet = {"items": [{"blind_review_id": "B1", "review_contract": {"allowed_decisions": ["CONFIRMED"], "allowed_confidence": ["HIGH"]}}]}
        response = {"review_type": REVIEW_TYPE, "reviewer": "OpenAI Codex independent blinded AI reviewer", "reviewed_at": "2026-10-01", "reviews": [{"blind_review_id": "B1", "decision": "CONFIRMED", "confidence": "HIGH", "rationale": "Aligned.", "evidence_checks": ["host"], "contradictions": []}]}
        self.assertEqual(validate_reviews(packet, response)[0]["blind_review_id"], "B1")


if __name__ == "__main__":
    unittest.main()
