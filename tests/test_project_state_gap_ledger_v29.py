import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "registry" / "analyses" / "project_state_gap_ledger_v29.json"


class ProjectStateGapLedgerV29Tests(unittest.TestCase):
    def test_v11_complete_and_original_capture_preserved(self) -> None:
        data = json.loads(LEDGER.read_text(encoding="utf-8"))
        for section in ("inputs", "implementation"):
            for item in data[section]:
                path = Path(item["path"])
                if not path.is_absolute():
                    path = ROOT / path
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["role"])
        state = data["state_amendments"]["P1_A2_V11"]
        self.assertEqual(state["resolved_results"], 115)
        self.assertEqual(state["unresolved_results"], 0)
        self.assertTrue(data["decision"]["a2_v11_execution_complete"])
        self.assertTrue(data["decision"]["supplemental_capture_plan_may_be_prepared"])
        self.assertFalse(data["decision"]["original_capture_plan_mutation_allowed"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
