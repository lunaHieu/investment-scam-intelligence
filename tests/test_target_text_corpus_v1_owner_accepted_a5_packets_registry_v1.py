import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "target_text_corpus_v1_owner_accepted_a5_packets_v1.json"


class OwnerAcceptedA5PacketsRegistryV1Tests(unittest.TestCase):
    def test_registry_pins_both_packets_without_claiming_human_review_or_admission(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"] + data["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item)
            self.assertEqual(sha256_file(path), item["sha256"], item)
        result = data["result"]
        self.assertEqual(result["records"], 42)
        self.assertEqual(result["language_records_pending_human_review"], 42)
        self.assertEqual(result["human_language_decisions_created"], 0)
        self.assertEqual(result["fresh_cohort_assertions_independently_verified"], 42)
        self.assertEqual(result["admission_credit_now"], 0)
        self.assertTrue(data["decision"]["a5_packet_preparation_complete"])
        self.assertFalse(data["decision"]["human_language_review_complete"])
        self.assertFalse(data["decision"]["partial_channel_contribution_allowed"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
