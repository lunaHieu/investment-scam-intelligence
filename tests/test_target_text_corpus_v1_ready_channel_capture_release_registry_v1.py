import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "target_text_corpus_v1_ready_channel_capture_release_v1.json"


class ReadyChannelCaptureReleaseRegistryV1Tests(unittest.TestCase):
    def test_registry_pins_all_release_inputs(self) -> None:
        value = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in value["inputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])

    def test_registry_keeps_downstream_gates_closed(self) -> None:
        value = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertTrue(value["decision"]["execution_allowed_in_separate_invocation"])
        self.assertFalse(value["decision"]["capture_executed_during_preparation"])
        self.assertFalse(value["decision"]["text_extraction_allowed"])
        self.assertFalse(value["decision"]["labeling_allowed"])


if __name__ == "__main__":
    unittest.main()
