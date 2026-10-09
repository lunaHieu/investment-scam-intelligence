import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_blind_second_review import verify


ROOT = Path(__file__).resolve().parents[1]
PILOT = Path(r"D:\nckh 2026-2027\ISI_Data\curated\target_text_corpus_v1_schema_review_pilot")


class TargetTextCorpusBlindSecondReviewTests(unittest.TestCase):
    def test_frozen_blind_second_review_passes(self) -> None:
        result = verify(
            ROOT / "configs" / "target_text_corpus_v1_blind_second_review_v1.json",
            PILOT / "blind_second_review_v1.json",
        )
        self.assertFalse(result["errors"], result["errors"])
        self.assertEqual(result["checks"]["reviewed_population"], 22)
        self.assertEqual(result["checks"]["second_recommendation_counts"], {"CONFIRMED": 4, "LEGITIMATE": 9, "UNCERTAIN": 9})
        self.assertTrue(result["decision"]["reconciliation_allowed"])
        self.assertFalse(result["decision"]["ground_truth_labeling_completed"])


if __name__ == "__main__":
    unittest.main()
