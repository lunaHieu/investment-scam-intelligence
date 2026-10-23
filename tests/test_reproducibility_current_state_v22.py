import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "registry" / "analyses" / "reproducibility_current_state_v22.json"


class ReproducibilityCurrentStateV22Tests(unittest.TestCase):
    def test_current_navigation_and_closed_gates(self) -> None:
        data = json.loads(STATE.read_text(encoding="utf-8"))
        for section in ("inputs", "implementation"):
            for item in data[section]:
                path = Path(item["path"])
                if not path.is_absolute():
                    path = ROOT / path
                self.assertTrue(path.is_file(), item["role"])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["role"])
        current = data["current_state"]
        self.assertEqual(current["c3_template_records"], 42)
        self.assertEqual(current["language_tasks_completed_by_human"], 0)
        self.assertEqual(current["fresh_v1_core_admitted_groups"], 0)
        self.assertTrue(data["decision"]["c3_preflight_complete"])
        self.assertFalse(data["decision"]["c3_human_response_complete"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
