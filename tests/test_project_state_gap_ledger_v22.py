import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "project_state_gap_ledger_v22.json"


class ProjectStateGapLedgerV22Tests(unittest.TestCase):
    def test_b4_is_current_without_opening_network_capture_or_models(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item)
            self.assertEqual(sha256_file(path), item["sha256"], item)
        b4 = data["state_amendments"]["P2_B4_READY_CHANNEL_AVAILABILITY_EXECUTION"]
        self.assertEqual(b4["release_records"], 70)
        self.assertEqual(b4["development_records"], 50)
        self.assertEqual(b4["external_holdout_records"], 20)
        self.assertEqual(b4["absolute_not_before_floor"], "2026-10-25T00:00:00+07:00")
        self.assertEqual(b4["minimum_a1_cooldown_seconds"], 86400)
        self.assertEqual(b4["minimum_delay_seconds"], 60.0)
        self.assertEqual(b4["maximum_attempts_per_candidate"], 1)
        self.assertEqual(b4["network_operations"], 0)
        self.assertTrue(data["decision"]["b4_complete"])
        self.assertTrue(data["decision"]["b5_execution_conditionally_prepared"])
        self.assertFalse(data["decision"]["network_execution_allowed_now"])
        self.assertFalse(data["decision"]["capture_allowed"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
