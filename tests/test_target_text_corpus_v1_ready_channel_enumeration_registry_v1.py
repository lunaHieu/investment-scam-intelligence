import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "target_text_corpus_v1_ready_channel_enumeration_v1.json"


class ReadyChannelEnumerationRegistryV1Tests(unittest.TestCase):
    def test_registry_pins_b1_preflight_and_closed_execution_gates(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "PASS_B1_TWO_READY_CHANNELS_CAPACITY_QUEUE_NOT_CREATED")
        for item in data["inputs"] + data["implementation"] + data["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item)
            self.assertEqual(sha256_file(path), item["sha256"], item)
        self.assertEqual(data["result"]["planned_candidates"], 70)
        self.assertEqual(data["result"]["candidates_selected"], 0)
        self.assertFalse(data["decision"]["candidate_queue_created"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
