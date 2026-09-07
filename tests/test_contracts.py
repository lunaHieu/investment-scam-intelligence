import unittest

from src.isi.contracts import assert_feature_columns, assert_gold_is_untouched


class ContractTests(unittest.TestCase):
    def test_safe_feature_columns_pass(self):
        assert_feature_columns({"text_embedding", "url_length", "ocr_token_count", "claim_roi"})

    def test_leakage_feature_is_rejected(self):
        with self.assertRaises(ValueError):
            assert_feature_columns({"text_embedding", "source_id"})

    def test_gold_cannot_be_used_for_tuning(self):
        with self.assertRaises(ValueError):
            assert_gold_is_untouched("gold", "select_threshold")

    def test_internal_test_remains_valid_for_evaluation(self):
        assert_gold_is_untouched("internal_test", "evaluate")


if __name__ == "__main__":
    unittest.main()
