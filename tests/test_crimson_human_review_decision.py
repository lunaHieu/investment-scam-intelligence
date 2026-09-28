import unittest

from scripts.record_crimson_human_review_decision import build_decision


class CrimsonHumanReviewDecisionTests(unittest.TestCase):
    def test_confirmed_first_review_keeps_second_review_and_training_gates_closed(self):
        brief = {
            "brief_id": "BRIEF_1",
            "pilot_id": "PILOT_1",
            "pilot_rank": 1,
            "crimson_host": "example.test",
            "current_live_reference_status": "ALL_URLS_LIVE_CONFIRMED",
            "recommended_human_decision": {
                "official_reference_checked": "YES",
                "identity_relationship": "IMPERSONATION_SUSPECTED",
                "evidence_assessment": "WARNING_RELEVANT",
                "second_review_required": "YES",
            },
            "workflow_state": {"human_confirmation_required": True},
        }
        decision = build_decision(brief, "Hieu", "2026-09-23", "Explicit user confirmation", "abc")
        self.assertEqual(decision["review_status"], "COMPLETED")
        self.assertEqual(decision["adjudication_status"], "SECOND_REVIEW_REQUIRED")
        self.assertEqual(decision["second_review_status"], "REQUESTED")
        self.assertEqual(decision["training_eligible"], "NO")
        self.assertFalse(decision["label_created"])

    def test_rejects_missing_human_confirmation_contract(self):
        brief = {
            "brief_id": "BRIEF_1",
            "pilot_id": "PILOT_1",
            "pilot_rank": 1,
            "crimson_host": "example.test",
            "current_live_reference_status": "ALL_URLS_LIVE_CONFIRMED",
            "recommended_human_decision": {"second_review_required": "YES"},
            "workflow_state": {"human_confirmation_required": False},
        }
        with self.assertRaises(ValueError):
            build_decision(brief, "Hieu", "2026-09-23", "Explicit user confirmation", "abc")


if __name__ == "__main__":
    unittest.main()
