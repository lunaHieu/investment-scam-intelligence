import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_manual_group_primary_review import verify


ROOT = Path(__file__).resolve().parents[1]
PILOT = Path(r"D:\nckh 2026-2027\ISI_Data\curated\target_text_corpus_v1_schema_review_pilot")


class TargetTextCorpusManualGroupPrimaryReviewTests(unittest.TestCase):
    def test_frozen_primary_group_review_passes_structural_qa(self) -> None:
        result = verify(
            ROOT / "configs" / "target_text_corpus_v1_manual_group_review_v1.json",
            PILOT / "manual_group_primary_review_v1.json",
        )
        self.assertFalse(result["errors"], result["errors"])
        self.assertEqual(result["checks"]["reviewed_population"], 22)
        self.assertEqual(result["checks"]["records_with_downstream_identity_or_content_flags"], 14)
        self.assertTrue(result["decision"]["primary_case_and_artifact_review_allowed"])
        self.assertFalse(result["decision"]["binary_labeling_completed"])


if __name__ == "__main__":
    unittest.main()
