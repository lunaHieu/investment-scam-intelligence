import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "registry" / "analyses" / "reproducibility_current_state_v25.json"


class ReproducibilityCurrentStateV25Tests(unittest.TestCase):
    def test_current_a1_complete_a2_waiting_navigation(self) -> None:
        data = json.loads(STATE.read_text(encoding="utf-8"))
        for section in ("inputs", "implementation"):
            for item in data[section]:
                path = Path(item["path"])
                if not path.is_absolute():
                    path = ROOT / path
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["role"])
        self.assertTrue(data["current_state"]["a1_complete"])
        self.assertTrue(data["current_state"]["a2_v11_release_verified"])
        self.assertFalse(data["current_state"]["a2_v11_network_executed"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
