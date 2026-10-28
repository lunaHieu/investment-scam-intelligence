import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_ready_channel_capture_release_v1 import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "target_text_corpus_v1_ready_channel_capture_result_v1.json"


class ReadyChannelCaptureResultRegistryV1Tests(unittest.TestCase):
    def test_registry_pins_partial_result_and_qa(self) -> None:
        value = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in value["inputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])

    def test_registry_routes_49_without_replaying_successes_or_failure(self) -> None:
        value = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(value["findings"]["captured_rows"], 3)
        self.assertEqual(value["findings"]["not_attempted_rows"], 49)
        self.assertFalse(value["decision"]["original_release_rerun_allowed"])
        self.assertFalse(value["decision"]["identical_failed_row_retry_allowed"])
        self.assertTrue(value["decision"]["exact_49_never_attempted_continuation_may_be_prepared"])


if __name__ == "__main__":
    unittest.main()
