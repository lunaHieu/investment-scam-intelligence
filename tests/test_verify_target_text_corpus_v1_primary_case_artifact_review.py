import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_primary_case_artifact_review import verify


ROOT = Path(__file__).resolve().parents[1]
PILOT = Path(r"D:\nckh 2026-2027\ISI_Data\curated\target_text_corpus_v1_schema_review_pilot")


class TargetTextCorpusPrimaryCaseArtifactReviewTests(unittest.TestCase):
    def test_frozen_primary_review_passes_structural_qa(self) -> None:
        result = verify(
            ROOT / "configs" / "target_text_corpus_v1_primary_case_artifact_review_v1.json",
            PILOT / "primary_case_artifact_review_v1.json",
        )
        self.assertFalse(result["errors"], result["errors"])
        self.assertEqual(result["checks"]["reviewed_population"], 22)
        self.assertEqual(result["checks"]["primary_recommendation_counts"], {"CONFIRMED": 4, "LEGITIMATE": 11, "UNCERTAIN": 7})
        self.assertTrue(result["decision"]["blind_independent_second_review_allowed"])
        self.assertFalse(result["decision"]["ground_truth_labeling_completed"])


if __name__ == "__main__":
    unittest.main()
