import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "project_state_gap_ledger_v14.json"


class ProjectStateGapLedgerV14Tests(unittest.TestCase):
    def test_ledger_records_retry_failure_and_closed_same_snapshot_path(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])

        sec = data["state_amendments"]["P1_SEC_IAPD"]
        self.assertEqual(sec["captured"], 57)
        self.assertEqual(sec["capture_failed_quarantined"], 1)
        self.assertEqual(sec["capture_retry_response_bytes"], 42)
        self.assertTrue(sec["capture_retry_repeat_failure"])
        self.assertEqual(sec["owner_accepted_labels"], 42)
        self.assertEqual(sec["training_eligible_records"], 0)
        self.assertFalse(data["decision"]["same_snapshot_retry_allowed"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
