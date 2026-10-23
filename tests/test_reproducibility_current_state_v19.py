import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "reproducibility_current_state_v19.json"


class ReproducibilityCurrentStateV19Tests(unittest.TestCase):
    def test_current_navigation_registers_b4_without_network_or_models(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "CURRENT_B4_CRASH_SAFE_EXACT_70_EXECUTION_RELEASE_NETWORK_CLOSED")
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item)
            self.assertEqual(sha256_file(path), item["sha256"], item)
        state = data["current_state"]
        self.assertEqual(state["ready_channel_availability_plan_records"], 70)
        self.assertEqual(state["ready_channel_availability_release_records"], 70)
        self.assertEqual(state["ready_channel_availability_executed_records"], 0)
        self.assertEqual(state["ready_channel_network_requests"], 0)
        self.assertFalse(state["a1_cdx_network_executed"])
        self.assertFalse(state["a2_v11_network_executed"])
        self.assertTrue(data["decision"]["b4_complete"])
        self.assertTrue(data["decision"]["b5_execution_conditionally_prepared"])
        self.assertFalse(data["decision"]["network_execution_allowed_now"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
