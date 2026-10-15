import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "registry" / "analyses" / "project_state_gap_ledger_v4.json"


class ProjectStateGapLedgerV4Tests(unittest.TestCase):
    def test_hashes_amendments_and_closed_gates(self) -> None:
        data = json.loads(LEDGER.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])
        crimson = data["state_amendments"]["P4_CRIMSON"]
        self.assertEqual(crimson["first_review_pending"], 39)
        self.assertEqual(crimson["second_review_population"], 21)
        self.assertEqual(crimson["blind_second_review_ready"], 1)
        self.assertEqual(crimson["official_reference_followup_current"], 15)
        self.assertEqual(crimson["human_decisions_created_by_packet_stage"], 0)
        preflight = data["state_amendments"]["P9_ACTIVE_MODULE_PREFLIGHT"]
        self.assertEqual(preflight["active_modules_passed"], 5)
        self.assertEqual(preflight["network_operations"], 0)
        self.assertTrue(data["decision"]["offline_parallel_preparation_exhausted_at_current_authority"])
        self.assertFalse(data["decision"]["network_execution_allowed_now"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
