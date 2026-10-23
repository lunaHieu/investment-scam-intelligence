import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "reproducibility_current_state_v20.json"


class ReproducibilityCurrentStateV20Tests(unittest.TestCase):
    def test_current_navigation_registers_a5_without_opening_data_or_model_gates(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "CURRENT_A5_EXACT_42_PACKETS_FRESH_QA_PASS_LANGUAGE_HUMAN_REVIEW_PENDING")
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item)
            self.assertEqual(sha256_file(path), item["sha256"], item)
        state = data["current_state"]
        self.assertEqual(state["fresh_cohort_assertions_verified"], 42)
        self.assertEqual(state["language_tasks_pending_human_review"], 42)
        self.assertEqual(state["human_language_decisions_created"], 0)
        self.assertEqual(state["fresh_v1_core_admitted_groups"], 0)
        self.assertEqual(state["ready_channel_availability_executed_records"], 0)
        self.assertTrue(data["decision"]["a5_packet_preparation_complete"])
        self.assertFalse(data["decision"]["human_language_review_complete"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
