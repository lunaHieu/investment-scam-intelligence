import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "registry" / "analyses" / "reproducibility_current_state_v26.json"


class ReproducibilityCurrentStateV26Tests(unittest.TestCase):
    def test_current_v11_complete_navigation(self) -> None:
        data = json.loads(STATE.read_text(encoding="utf-8"))
        for section in ("inputs", "implementation"):
            for item in data[section]:
                path = Path(item["path"])
                if not path.is_absolute():
                    path = ROOT / path
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["role"])
        current = data["current_state"]
        self.assertEqual(current["availability_resolved"], 115)
        self.assertEqual(current["availability_unresolved"], 0)
        self.assertTrue(current["v11_supplemental_complete"])
        self.assertFalse(current["original_capture_plan_mutated"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
