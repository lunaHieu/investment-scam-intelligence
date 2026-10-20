import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "registry" / "analyses" / "project_state_gap_ledger_v10.json"


class ProjectStateGapLedgerV10Tests(unittest.TestCase):
    def test_hashes_partial_resolved_capture_state_and_gates(self) -> None:
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
        self.assertEqual(sec["capture_plan_rows"], 58)
        self.assertEqual(sec["capture_plan_by_cohort"], {"DEVELOPMENT": 46, "EXTERNAL_HOLDOUT": 12})
        self.assertEqual(sec["quarantined_unresolved"], 2)
        self.assertEqual(sec["capture_not_before"], "2026-10-21T14:19:54.213531+07:00")
        self.assertTrue(sec["capture_release_qa_passed"])

        self.assertFalse(data["decision"]["network_execution_allowed_now"])
        self.assertFalse(data["decision"]["capture_allowed_now"])
        self.assertTrue(data["decision"]["capture_allowed_at_or_after_not_before"])
        self.assertFalse(data["decision"]["live_candidate_domain_access_allowed"])
        self.assertFalse(data["decision"]["validation_or_test_opening_allowed"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
