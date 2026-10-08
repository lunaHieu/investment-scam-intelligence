import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_wayback_capture_retry_v2 import verify_registry


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = (
    ROOT
    / "registry"
    / "analyses"
    / "target_text_corpus_v1_wayback_capture_retry_v2.json"
)


class TargetTextCorpusWaybackCaptureRetryVerifierTests(unittest.TestCase):
    def test_frozen_retry_registry_passes(self) -> None:
        result = verify_registry(REGISTRY)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["retry_candidate_count"], 29)
        self.assertTrue(result["cooldown_ready"])
        self.assertFalse(result["text_extraction_allowed"])


if __name__ == "__main__":
    unittest.main()
