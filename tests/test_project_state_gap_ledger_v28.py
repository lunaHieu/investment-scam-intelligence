import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "registry" / "analyses" / "project_state_gap_ledger_v28.json"


class ProjectStateGapLedgerV28Tests(unittest.TestCase):
    def test_a1_complete_and_a2_frozen(self) -> None:
        data = json.loads(LEDGER.read_text(encoding="utf-8"))
        for section in ("inputs", "implementation"):
            for item in data[section]:
                path = Path(item["path"])
                if not path.is_absolute():
                    path = ROOT / path
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["role"])
        self.assertTrue(data["decision"]["a1_complete"])
        self.assertTrue(data["decision"]["a2_v11_release_verified"])
        self.assertFalse(data["decision"]["a2_network_gate_open_at_snapshot"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
