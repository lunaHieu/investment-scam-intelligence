import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "project_state_gap_ledger_v23.json"


class ProjectStateGapLedgerV23Tests(unittest.TestCase):
    def test_a5_is_current_without_claiming_human_review_or_admission(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item)
            self.assertEqual(sha256_file(path), item["sha256"], item)
        a5 = data["state_amendments"]["P2_A5_OWNER_ACCEPTED_ADMISSION_PACKETS"]
        self.assertEqual(a5["population_records"], 42)
        self.assertEqual(a5["fresh_cohort_assertions_verified"], 42)
        self.assertEqual(a5["language_tasks_pending_human_review"], 42)
        self.assertEqual(a5["human_language_decisions_created"], 0)
        self.assertEqual(a5["admission_credit_now"], 0)
        self.assertTrue(data["decision"]["a5_packet_preparation_complete"])
        self.assertFalse(data["decision"]["human_language_review_complete"])
        self.assertFalse(data["decision"]["network_execution_allowed_now"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
