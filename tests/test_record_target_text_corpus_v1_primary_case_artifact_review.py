import unittest
from collections import Counter
from pathlib import Path

from scripts.record_target_text_corpus_v1_primary_case_artifact_review import JUDGMENTS, build_review


ROOT = Path(__file__).resolve().parents[1]


class RecordTargetTextCorpusPrimaryCaseArtifactReviewTests(unittest.TestCase):
    def test_judgments_cover_frozen_population_and_are_conservative(self) -> None:
        review = build_review(ROOT / "configs" / "target_text_corpus_v1_primary_case_artifact_review_v1.json")
        self.assertEqual(len(review["records"]), 22)
        self.assertEqual(len(JUDGMENTS), 22)
        self.assertTrue(all(row["ground_truth_status"] == "UNCERTAIN" for row in review["records"]))
        self.assertTrue(all(row["label_created"] is False for row in review["records"]))
        self.assertTrue(all(row["training_eligible"] == "NO" for row in review["records"]))

    def test_expected_recommendation_distribution(self) -> None:
        counts = Counter(item["primary_recommendation"] for item in JUDGMENTS.values())
        self.assertEqual(counts, {"CONFIRMED": 4, "LEGITIMATE": 11, "UNCERTAIN": 7})


if __name__ == "__main__":
    unittest.main()
