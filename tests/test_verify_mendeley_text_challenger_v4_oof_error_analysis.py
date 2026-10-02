import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "verify_mendeley_text_challenger_v4_oof_error_analysis.py"
REPORT_PATH = Path(
    r"D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026"
    r"\group_split_v2\text_challenger_v4\error_analysis"
    r"\text_challenger_v4_train_oof_error_analysis.json"
)
SPEC = importlib.util.spec_from_file_location("verify_semantic_v4_oof_errors", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class VerifySemanticChallengerV4OOFErrorAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = MODULE.verify(REPORT_PATH)

    def test_analysis_outputs_reproduce(self):
        self.assertTrue(self.report["valid"], self.report["errors"])
        self.assertEqual(self.report["row_count"], 3916)
        self.assertEqual(self.report["review_queue_count"], 60)

    def test_transition_counts_are_frozen(self):
        self.assertEqual(
            self.report["transition_counts"],
            {
                "both_correct": 2258,
                "e5_regression": 567,
                "e5_recovery": 444,
                "both_wrong": 647,
            },
        )

    def test_no_model_or_validation_access(self):
        self.assertFalse(self.report["validation_opened"])
        self.assertEqual(self.report["model_fit_operations"], 0)


if __name__ == "__main__":
    unittest.main()
