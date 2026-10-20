import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "project_execution_sequence_v1.json"


class ProjectExecutionSequenceV1Tests(unittest.TestCase):
    def test_sequence_pins_current_state_and_preserves_gates(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])

        phases = data["ordered_main_phases"]
        self.assertEqual([phase["order"] for phase in phases], list(range(1, 11)))
        self.assertEqual(phases[0]["phase"], "V9_AVAILABILITY_AND_V5_CAPTURE")
        self.assertEqual(phases[-1]["phase"], "DEVELOPMENT_SPLIT_AND_MODEL_CANDIDATE_FREEZE")
        self.assertEqual(data["current_counts"]["fresh_v1_core_validated_groups"], 0)
        self.assertEqual(data["current_counts"]["fresh_v1_core_required_groups"], 300)
        self.assertEqual(data["current_counts"]["sec_iapd_capture_rows"], 58)
        self.assertEqual(data["current_counts"]["sec_iapd_capture_by_cohort"], {"DEVELOPMENT": 46, "EXTERNAL_HOLDOUT": 12})

        decision = data["decision"]
        self.assertTrue(decision["research_documentation_allowed_now"])
        self.assertTrue(decision["crimson_handoff_preparation_allowed_now"])
        self.assertFalse(decision["crimson_human_decisions_may_be_fabricated"])
        self.assertFalse(decision["validation_or_test_opening_allowed"])
        self.assertFalse(decision["training_allowed"])


if __name__ == "__main__":
    unittest.main()
