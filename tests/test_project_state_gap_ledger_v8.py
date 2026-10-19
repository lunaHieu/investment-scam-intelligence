import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "registry" / "analyses" / "project_state_gap_ledger_v8.json"


class ProjectStateGapLedgerV8Tests(unittest.TestCase):
    def test_hashes_current_v8_state_and_closed_gates(self) -> None:
        data = json.loads(LEDGER.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])

        sec = data["state_amendments"]["P1_SEC_IAPD"]
        self.assertEqual(
            (sec["planned"], sec["resolved"], sec["available"], sec["unavailable"], sec["unresolved"]),
            (115, 113, 58, 55, 2),
        )
        self.assertEqual(sec["cumulative_network_requests_through_v7"], 164)
        self.assertTrue(sec["v7_stopped_on_http_429"])
        self.assertEqual(sec["v8_retry_rows"], 2)
        self.assertEqual(sec["v8_authoritative_executor"], "scripts.retry_sec_edgar_iapd_wayback_availability_v8")
        self.assertEqual(sec["capture_tooling_for_complete_v8"], "NOT_YET_FROZEN")
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
