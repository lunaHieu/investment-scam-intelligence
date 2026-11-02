from __future__ import annotations

import unittest

from scripts.verify_crimson_official_source_followup_v3 import verify


class CrimsonOfficialSourceFollowupV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = verify()

    def test_addendum_passes_independent_offline_verification(self) -> None:
        self.assertEqual(
            self.result["status"],
            "PASS_ALTERNATE_OFFICIAL_FACT_PINNED_PRIMARY_REVIEW_STILL_PENDING",
        )
        self.assertEqual(self.result["errors"], [])

    def test_one_exact_official_fact_is_added_without_decision(self) -> None:
        checks = self.result["checks"]
        self.assertEqual(checks["fact_rows"], 1)
        self.assertEqual(checks["pilot_ids_with_new_fact"], 1)
        self.assertEqual(checks["direct_official_documents_read"], 1)
        self.assertEqual(checks["primary_reviews_completed"], 0)
        self.assertEqual(checks["previously_blocked_url_retries"], 0)

    def test_label_admission_and_candidate_access_remain_closed(self) -> None:
        checks = self.result["checks"]
        self.assertEqual(checks["candidate_domain_accesses"], 0)
        self.assertEqual(checks["labels_created"], 0)
        self.assertEqual(checks["dataset_rows_admitted"], 0)
        self.assertEqual(checks["training_eligible"], 0)


if __name__ == "__main__":
    unittest.main()
