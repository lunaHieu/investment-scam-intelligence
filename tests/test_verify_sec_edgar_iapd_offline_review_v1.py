import unittest

from scripts.verify_sec_edgar_iapd_offline_review_v1 import independent_classification, independent_core


class VerifySecEdgarIapdOfflineReviewV1Tests(unittest.TestCase):
    def test_independent_core_normalizes_legal_suffixes(self) -> None:
        self.assertEqual(independent_core("The Alpha Advisors, L.L.C."), ["alpha", "advisors"])

    def test_independent_classification_holds_descriptor_mismatch(self) -> None:
        status, recommendation, _, _ = independent_classification("1248 Management LLC", "1248 Partners LLC", 0.8)
        self.assertEqual(status, "OFFLINE_AMBIGUOUS_RELATED_NAME_CAUTION")
        self.assertEqual(recommendation, "HOLD_FOR_DEEPER_IDENTITY_REVIEW")


if __name__ == "__main__":
    unittest.main()
