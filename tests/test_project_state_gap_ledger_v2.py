import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "registry" / "analyses" / "project_state_gap_ledger_v2.json"


class ProjectStateGapLedgerV2Tests(unittest.TestCase):
    def test_hashes_state_transitions_and_closed_gates(self) -> None:
        data = json.loads(LEDGER.read_text(encoding="utf-8"))
        for item in data["inputs"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])
        self.assertTrue(data["state"]["raw"]["complete"])
        self.assertEqual(data["state"]["raw"]["git_rooted_hash_chain_count"], 278)
        self.assertEqual(data["state"]["external_21"]["diagnostic_reporting_eligible"], 21)
        self.assertFalse(data["state"]["external_21"]["independent_human_evidence_rereview"])
        self.assertEqual(data["state"]["crimson"]["human_first_reviews_remaining"], 39)
        self.assertEqual(data["state"]["target_text_pilot"]["training_eligible"], 0)
        self.assertFalse(data["state"]["target_text_pilot"]["development_corpus_gate_met"])
        self.assertEqual(data["state"]["vietnamese"]["verified_supply"], 0)
        self.assertFalse(data["decision"]["training_allowed"])
        self.assertFalse(data["decision"]["validation_or_test_opening_allowed"])


if __name__ == "__main__":
    unittest.main()
