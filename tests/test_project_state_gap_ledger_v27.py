import hashlib, json, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "registry" / "analyses" / "project_state_gap_ledger_v27.json"

class ProjectStateGapLedgerV27Tests(unittest.TestCase):
    def test_owner_override_ready_and_execution_pending(self):
        data = json.loads(LEDGER.read_text(encoding="utf-8"))
        for section in ("inputs", "implementation"):
            for item in data[section]:
                path = Path(item["path"])
                if not path.is_absolute(): path = ROOT / path
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"])
        self.assertTrue(data["decision"]["a1_owner_timing_override_verified"])
        self.assertFalse(data["decision"]["a1_network_executed"])
        self.assertFalse(data["decision"]["training_allowed"])

if __name__ == "__main__": unittest.main()
