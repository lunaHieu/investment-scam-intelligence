import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_exact_text_result_registry_v1 import verify_registry


ROOT = Path(__file__).resolve().parents[1]


class TargetTextCorpusExactTextResultRegistryV1Tests(unittest.TestCase):
    def test_frozen_registry_and_outputs_pass(self) -> None:
        result = verify_registry(
            ROOT / "registry" / "analyses" / "target_text_corpus_v1_exact_text_result_v1.json"
        )
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["extracted_count"], 23)
        self.assertEqual(result["minimum_content_passed_count"], 22)
        self.assertFalse(result["human_label_review_allowed"])


if __name__ == "__main__":
    unittest.main()
