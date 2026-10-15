import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "registry" / "analyses" / "project_state_gap_ledger_v3.json"


class ProjectStateGapLedgerV3Tests(unittest.TestCase):
    def test_hashes_completed_parallel_work_and_remaining_gates(self) -> None:
        data = json.loads(LEDGER.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])
        state = data["current_state"]
        self.assertEqual(state["P2_RAW_QA"]["status"], "COMPLETE")
        self.assertTrue(state["P3_EXTERNAL_21"]["module_compatible_verifier"])
        self.assertFalse(state["P3_EXTERNAL_21"]["independent_human_evidence_rereview"])
        self.assertTrue(state["P6_MANUAL_ACQUISITION"]["packet_verified"])
        self.assertFalse(state["P6_MANUAL_ACQUISITION"]["ssc_acquisition_open"])
        self.assertFalse(state["P6_MANUAL_ACQUISITION"]["hnx_acquisition_open"])
        self.assertFalse(state["P7_MODEL_CHOICE"]["new_model_configuration_authorized"])
        self.assertEqual(len(data["remaining_gate_schedule"]), 3)
        self.assertEqual(
            data["remaining_gate_schedule"][0]["earliest_action"],
            "2026-10-16T00:48:55.969405+07:00",
        )
        self.assertTrue(data["decision"]["parallel_offline_preparation_complete"])
        self.assertFalse(data["decision"]["training_allowed"])
        self.assertFalse(data["decision"]["validation_or_test_opening_allowed"])

    def test_documentation_is_registered_after_hash_freeze(self) -> None:
        documentation = ROOT / "docs" / "project-state-gap-ledger-v3.md"
        self.assertTrue(documentation.is_file())
        text = documentation.read_text(encoding="utf-8")
        self.assertIn("P1R", text)
        self.assertIn("2026-10-16T00:48:55.969405+07:00", text)


if __name__ == "__main__":
    unittest.main()
