import hashlib, json, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "registry" / "analyses" / "reproducibility_current_state_v24.json"

class ReproducibilityCurrentStateV24Tests(unittest.TestCase):
    def test_current_override_navigation(self):
        data = json.loads(STATE.read_text(encoding="utf-8"))
        for section in ("inputs", "implementation"):
            for item in data[section]:
                path = Path(item["path"])
                if not path.is_absolute(): path = ROOT / path
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"])
        self.assertTrue(data["decision"]["a1_owner_timing_override_verified"])
        self.assertFalse(data["current_state"]["a1_network_executed"])
        self.assertFalse(data["decision"]["training_allowed"])

if __name__ == "__main__": unittest.main()
