import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_post_capture_grouping_result_registry_v1 import verify_registry


ROOT = Path(__file__).resolve().parents[1]


class TargetTextCorpusPostCaptureGroupingResultRegistryTests(unittest.TestCase):
    def test_registered_result_passes(self) -> None:
        result = verify_registry(
            ROOT / "registry" / "analyses" / "target_text_corpus_v1_post_capture_grouping_result_v1.json"
        )
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["minimum_content_pass_rows"], 22)
        self.assertEqual(result["transitive_exclusion_groups"], 22)
        self.assertFalse(result["human_label_review_allowed"])


if __name__ == "__main__":
    unittest.main()
