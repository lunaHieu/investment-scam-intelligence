import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_wayback_capture_result_registry_v2 import (
    verify_registry,
)


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = (
    ROOT
    / "registry"
    / "analyses"
    / "target_text_corpus_v1_wayback_capture_result_v2.json"
)


class TargetTextCorpusWaybackCaptureResultRegistryV2Tests(unittest.TestCase):
    def test_frozen_capture_result_registry_passes(self) -> None:
        result = verify_registry(REGISTRY)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["captured_count"], 23)
        self.assertEqual(result["failed_count"], 6)
        self.assertFalse(result["binary_labeling_allowed"])


if __name__ == "__main__":
    unittest.main()
