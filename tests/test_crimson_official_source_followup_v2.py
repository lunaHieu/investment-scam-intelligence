from __future__ import annotations

import unittest

from scripts.verify_crimson_official_source_followup_v2 import verify


class CrimsonOfficialSourceFollowupV2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = verify()

    def test_independent_offline_verification_passes(self) -> None:
        self.assertEqual(
            self.result["status"],
            "PASS_OFFICIAL_FACTS_PINNED_REVIEW_AND_ADMISSION_STILL_CLOSED",
        )
        self.assertEqual(self.result["errors"], [])

    def test_source_counts_and_identity_limits_are_preserved(self) -> None:
        checks = self.result["checks"]
        self.assertEqual(checks["official_source_fact_rows"], 12)
        self.assertEqual(checks["unique_pilots_with_new_facts"], 11)
        self.assertEqual(checks["unique_official_pages_directly_read"], 11)
        self.assertEqual(checks["followup_status_rows"], 15)
        self.assertEqual(checks["root_only_relationships_kept_unresolved"], 3)

    def test_no_review_decision_or_admission_was_created(self) -> None:
        checks = self.result["checks"]
        self.assertEqual(checks["primary_reviews_completed"], 0)
        self.assertEqual(checks["independent_second_reviews_completed"], 0)
        self.assertEqual(checks["same_url_retries"], 0)
        self.assertEqual(checks["candidate_domain_accesses"], 0)
        self.assertEqual(checks["labels_created"], 0)
        self.assertEqual(checks["dataset_rows_admitted"], 0)
        self.assertEqual(checks["training_eligible"], 0)


if __name__ == "__main__":
    unittest.main()
