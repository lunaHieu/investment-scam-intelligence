import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "registry" / "analyses" / "reproducibility_current_state_v27.json"


class ReproducibilityCurrentStateV27Tests(unittest.TestCase):
    def test_v11_supplemental_gate_is_separate_and_closed_until_not_before(self) -> None:
        data = json.loads(STATE.read_text(encoding="utf-8"))
        current = data["current_state"]
        self.assertEqual(current["availability_total"], 115)
        self.assertEqual(current["availability_available"], 60)
        self.assertEqual(current["availability_unresolved"], 0)
        self.assertEqual(current["supplemental_plan_rows"], 2)
        self.assertFalse(data["decision"]["original_capture_plan_mutation_allowed"])
        self.assertFalse(data["decision"]["capture_allowed_now"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
