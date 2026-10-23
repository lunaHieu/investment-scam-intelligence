import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "project_state_gap_ledger_v21.json"


class ProjectStateGapLedgerV21Tests(unittest.TestCase):
    def test_b3_is_current_without_opening_execution_capture_or_models(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item)
            self.assertEqual(sha256_file(path), item["sha256"], item)
        b3 = data["state_amendments"]["P2_B3_READY_CHANNEL_AVAILABILITY_PLAN"]
        self.assertEqual(b3["plan_records"], 70)
        self.assertEqual(b3["development_records"], 50)
        self.assertEqual(b3["external_holdout_records"], 20)
        self.assertEqual(b3["unique_hosts"], 70)
        self.assertEqual(b3["unique_normalized_entities"], 70)
        self.assertEqual(b3["development_holdout_host_overlap"], 0)
        self.assertEqual(b3["development_holdout_entity_overlap"], 0)
        self.assertEqual(b3["network_operations"], 0)
        self.assertEqual(b3["future_minimum_delay_seconds"], 60.0)
        self.assertTrue(data["decision"]["b4_execution_release_preparation_allowed"])
        self.assertFalse(data["decision"]["network_execution_allowed"])
        self.assertFalse(data["decision"]["capture_allowed"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
