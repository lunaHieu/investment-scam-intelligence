import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "target_text_corpus_v1_ready_channel_queue_v1.json"


class ReadyChannelQueueRegistryV1Tests(unittest.TestCase):
    def test_registry_pins_complete_disjoint_unlabeled_b2_outputs(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"] + data["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item)
            self.assertEqual(sha256_file(path), item["sha256"], item)
        result = data["result"]
        self.assertEqual(result["candidate_records"], 70)
        self.assertEqual(result["development_records"], 50)
        self.assertEqual(result["external_holdout_records"], 20)
        self.assertEqual(result["unique_hosts"], 70)
        self.assertEqual(result["unique_normalized_entities"], 70)
        self.assertEqual(result["development_holdout_host_overlap"], 0)
        self.assertEqual(result["development_holdout_entity_overlap"], 0)
        self.assertEqual(result["uncertain_records"], 70)
        self.assertEqual(result["labels_created"], 0)
        self.assertTrue(data["decision"]["b3_offline_wayback_availability_release_may_be_prepared"])
        self.assertFalse(data["decision"]["wayback_query_allowed"])
        self.assertFalse(data["decision"]["artifact_capture_allowed"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
