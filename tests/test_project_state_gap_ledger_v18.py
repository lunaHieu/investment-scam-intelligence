import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "project_state_gap_ledger_v18.json"


class ProjectStateGapLedgerV18Tests(unittest.TestCase):
    def test_current_ledger_registers_a4_and_preserves_closed_gates(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "FROZEN_A4_REPAIR_PROTOCOL_A1_A2_GATES_UNCHANGED")
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item)
            self.assertEqual(sha256_file(path), item["sha256"], item)
        repair = data["state_amendments"]["P2_A4_ADMISSION_REPAIR"]
        self.assertEqual(repair["records_audited"], 42)
        self.assertEqual(repair["human_review_now_blockers"], 1)
        self.assertEqual(repair["offline_assertion_now_blockers"], 1)
        self.assertEqual(repair["full_channel_or_population_blockers"], 7)
        self.assertEqual(repair["fields_credited_now"], 0)
        self.assertEqual(repair["v1_core_admitted_records"], 0)
        self.assertFalse(data["state_amendments"]["P1_SEC_IAPD"]["a1_cdx_network_executed"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
