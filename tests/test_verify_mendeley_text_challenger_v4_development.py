import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "verify_mendeley_text_challenger_v4_development.py"
RESULT_PATH = Path(
    r"D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026"
    r"\group_split_v2\text_challenger_v4\development"
    r"\text_challenger_v4_development_oof_result.json"
)
SPEC = importlib.util.spec_from_file_location("verify_semantic_v4_development", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class VerifySemanticChallengerV4DevelopmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = MODULE.verify(RESULT_PATH)

    def test_development_artifacts_are_valid(self):
        self.assertTrue(self.report["valid"], self.report["errors"])
        self.assertEqual(self.report["prediction_count"], 3916)
        self.assertEqual(self.report["unique_group_count"], 3783)

    def test_all_reproducible_performance_gates_failed(self):
        self.assertEqual(
            self.report["independently_verified_failed_performance_gates"],
            [
                "maximum_single_source_macro_f1_decline",
                "pooled_macro_f1_delta_minimum",
                "source_mean_macro_f1_delta_minimum",
                "worst_source_macro_f1_delta_minimum",
            ],
        )
        self.assertEqual(len(self.report["all_stored_failed_gates"]), 6)

    def test_validation_remains_closed(self):
        self.assertFalse(self.report["validation_opened"])
        self.assertIn("REJECTED", self.report["status"])


if __name__ == "__main__":
    unittest.main()
