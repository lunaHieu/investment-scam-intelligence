import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "registry" / "analyses" / "project_state_gap_ledger_v30.json"


class ProjectStateGapLedgerV30Tests(unittest.TestCase):
    def test_supplemental_capture_preparation_is_complete_but_execution_waits(self) -> None:
        data = json.loads(LEDGER.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "CURRENT_V11_SUPPLEMENTAL_CAPTURE_PLAN_RELEASE_FROZEN")
        self.assertTrue(data["decision"]["supplemental_capture_plan_qa_passed"])
        self.assertTrue(data["decision"]["supplemental_capture_release_qa_passed"])
        self.assertFalse(data["decision"]["capture_allowed_now"])
        self.assertTrue(data["decision"]["original_capture_plan_mutation_allowed"] is False)
        self.assertTrue(data["decision"]["original_review_population_mutation_allowed"] is False)
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
