import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "project_state_gap_ledger_v11.json"


class ProjectStateGapLedgerV11Tests(unittest.TestCase):
    def test_ledger_records_v9_rate_limit_and_v10_gate(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])

        sec = data["state_amendments"]["P1_SEC_IAPD"]
        self.assertEqual(sec["resolved"], 113)
        self.assertEqual(sec["unresolved"], 2)
        self.assertEqual(sec["cumulative_network_requests_through_v9"], 167)
        self.assertTrue(sec["v9_stopped_on_http_429"])
        self.assertEqual(sec["v10_not_before"], "2026-10-22T18:18:58.983066+07:00")
        self.assertTrue(sec["capture_release_v5_preserved"])
        self.assertFalse(sec["capture_executed"])

        decision = data["decision"]
        self.assertFalse(decision["network_execution_allowed_now"])
        self.assertFalse(decision["training_allowed"])


if __name__ == "__main__":
    unittest.main()
