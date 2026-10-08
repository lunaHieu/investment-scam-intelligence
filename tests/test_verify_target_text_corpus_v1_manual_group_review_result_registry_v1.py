import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_manual_group_review_result_registry_v1 import verify_registry


ROOT = Path(__file__).resolve().parents[1]


class TargetTextCorpusManualGroupReviewResultRegistryTests(unittest.TestCase):
    def test_registered_result_passes(self) -> None:
        result = verify_registry(
            ROOT / "registry" / "analyses" / "target_text_corpus_v1_manual_group_review_result_v1.json"
        )
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["reviewed_records"], 22)
        self.assertEqual(result["records_with_downstream_flags"], 14)
        self.assertFalse(result["binary_labeling_completed"])


if __name__ == "__main__":
    unittest.main()
