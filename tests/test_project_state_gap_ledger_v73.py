import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "registry/analyses/project_state_gap_ledger_v73.json"


class ProjectStateGapLedgerV73Tests(unittest.TestCase):
    def test_offline_findings_and_closed_gates_are_hash_pinned(self):
        data = json.loads(LEDGER.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])

        self.assertFalse(data["state_amendments"]["PBC05"]["exact_cause_recoverable"])
        self.assertFalse(data["state_amendments"]["PBC08"]["exact_live_key_recoverable"])
        self.assertEqual(data["state_amendments"]["synthetic_offline_tests_passed"], 5)
        self.assertEqual(data["state_amendments"]["rows_admitted"], 0)
        self.assertFalse(data["decision"]["new_source_request_authorized"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
