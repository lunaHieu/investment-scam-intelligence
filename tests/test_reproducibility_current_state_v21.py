import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "reproducibility_current_state_v21.json"


class ReproducibilityCurrentStateV21Tests(unittest.TestCase):
    def test_current_navigation_registers_c1_without_opening_execution(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "CURRENT_C1_OFFLINE_SCOPE_FROZEN_EXTERNAL_INPUTS_STILL_REQUIRED")
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item)
            self.assertEqual(sha256_file(path), item["sha256"], item)
        state = data["current_state"]
        self.assertEqual(state["fresh_v1_core_admitted_groups"], 0)
        self.assertEqual(state["conditional_residual_gap"], 258)
        self.assertEqual(state["c1_source_files_acquired"], 0)
        self.assertEqual(state["language_tasks_pending_human_review"], 42)
        self.assertEqual(state["ready_channel_availability_executed_records"], 0)
        self.assertTrue(data["decision"]["c1_complete"])
        self.assertFalse(data["decision"]["network_execution_allowed_now"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
