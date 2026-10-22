import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "project_state_gap_ledger_v16.json"


class ProjectStateGapLedgerV16Tests(unittest.TestCase):
    def test_current_ledger_registers_both_offline_branches_without_opening_network(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "FROZEN_A1_RELEASE_AND_A2_TOOLING_NETWORK_GATES_SEPARATE")
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item)
            self.assertEqual(sha256_file(path), item["sha256"], item)
        sec = data["state_amendments"]["P1_SEC_IAPD"]
        self.assertTrue(sec["a1_cdx_concrete_release_frozen"])
        self.assertTrue(sec["a2_v11_tooling_frozen"])
        self.assertFalse(sec["a2_v11_concrete_release_created"])
        self.assertEqual(sec["a2_v11_ordered_retry_ids"], [
            "TTCV1_EDGAR_AVAIL_HOLDOUT_011", "TTCV1_EDGAR_AVAIL_HOLDOUT_018"
        ])
        self.assertFalse(data["decision"]["network_execution_performed"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
