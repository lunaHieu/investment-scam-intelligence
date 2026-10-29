import unittest

from scripts.verify_target_text_corpus_v1_sanitized_text_source_review_reconciliation_v1 import verify


class SanitizedTextSourceReviewReconciliationV1Tests(unittest.TestCase):
    def test_reconciliation_is_conservative_and_reproducible(self) -> None:
        self.assertEqual(verify(), {"status":"PASS_RECONCILIATION_ZERO_REAL_WORLD_ACQUISITION_READY","reviewed_sources":6})


if __name__ == "__main__":
    unittest.main()
