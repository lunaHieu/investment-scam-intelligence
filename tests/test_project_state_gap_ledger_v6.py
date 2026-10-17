import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "registry" / "analyses" / "project_state_gap_ledger_v6.json"


class ProjectStateGapLedgerV6Tests(unittest.TestCase):
    def test_hashes_current_v6_state_and_closed_gates(self) -> None:
        data = json.loads(LEDGER.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])

        sec = data["state_amendments"]["P1_SEC_IAPD"]
        self.assertEqual(sec["planned"], 115)
        self.assertEqual(sec["resolved"], 107)
        self.assertEqual(sec["available"], 52)
        self.assertEqual(sec["unavailable"], 55)
        self.assertEqual(sec["unresolved"], 8)
        self.assertEqual(sec["external_holdout_unresolved"], 4)
        self.assertEqual(sec["cumulative_network_requests_through_v5"], 156)
        self.assertFalse(sec["v5_stopped_on_http_429"])
        self.assertEqual(sec["v6_retry_rows"], 8)
        self.assertEqual(sec["v6_minimum_delay_seconds"], 60.0)
        self.assertFalse(sec["capture_plan_allowed"])

        self.assertTrue(data["decision"]["offline_parallel_preparation_exhausted_at_current_authority"])
        for gate in (
            "network_execution_allowed_now",
            "live_candidate_domain_access_allowed",
            "capture_allowed",
            "validation_or_test_opening_allowed",
            "training_allowed",
            "model_scoring_allowed",
        ):
            self.assertFalse(data["decision"][gate])


if __name__ == "__main__":
    unittest.main()
