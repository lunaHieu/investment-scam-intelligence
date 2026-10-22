import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "project_state_gap_ledger_v12.json"


class ProjectStateGapLedgerV12Tests(unittest.TestCase):
    def test_ledger_records_capture_review_acceptance_and_closed_training(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])

        sec = data["state_amendments"]["P1_SEC_IAPD"]
        self.assertEqual(sec["capture_planned"], 58)
        self.assertEqual(sec["captured"], 57)
        self.assertEqual(sec["reviewable"], 56)
        self.assertEqual(sec["owner_accepted_labels"], 42)
        self.assertEqual(sec["uncertain_retained"], 14)
        self.assertEqual(sec["accepted_by_cohort"], {"DEVELOPMENT": 33, "EXTERNAL_HOLDOUT": 9})
        self.assertEqual(sec["training_eligible_records"], 0)
        self.assertEqual(data["state_amendments"]["P2_DATA_SUFFICIENCY"]["fresh_v1_core_admitted_groups"], 0)
        self.assertTrue(data["decision"]["capacity_gap_update_allowed_now"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
