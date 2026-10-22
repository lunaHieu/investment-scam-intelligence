import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "project_state_gap_ledger_v13.json"


class ProjectStateGapLedgerV13Tests(unittest.TestCase):
    def test_ledger_records_v10_rate_limit_and_preserves_completed_state(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])

        sec = data["state_amendments"]["P1_SEC_IAPD"]
        self.assertEqual(sec["availability_resolved"], 113)
        self.assertEqual(sec["availability_unresolved"], 2)
        self.assertTrue(sec["v10_stopped_on_http_429"])
        self.assertEqual(sec["captured"], 57)
        self.assertEqual(sec["reviewable"], 56)
        self.assertEqual(sec["owner_accepted_labels"], 42)
        self.assertEqual(sec["training_eligible_records"], 0)
        self.assertFalse(data["decision"]["capture_retry_allowed_in_v10_run"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
