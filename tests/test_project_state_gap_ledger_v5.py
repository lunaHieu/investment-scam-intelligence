import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "registry" / "analyses" / "project_state_gap_ledger_v5.json"


class ProjectStateGapLedgerV5Tests(unittest.TestCase):
    def test_hashes_current_sec_state_and_closed_gates(self) -> None:
        data = json.loads(LEDGER.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                item["sha256"],
                item["path"],
            )
        sec = data["state_amendments"]["P1_SEC_IAPD"]
        self.assertEqual(sec["planned"], 115)
        self.assertEqual(sec["resolved"], 92)
        self.assertEqual(sec["available"], 45)
        self.assertEqual(sec["unavailable"], 47)
        self.assertEqual(sec["unresolved"], 23)
        self.assertTrue(sec["v4_stopped_on_http_429"])
        self.assertEqual(sec["v5_minimum_delay_seconds"], 60.0)
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
