import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "project_state_gap_ledger_v15.json"


class ProjectStateGapLedgerV15Tests(unittest.TestCase):
    def test_current_ledger_preserves_counts_and_registers_closed_cdx_gate(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "FROZEN_CDX_RELEASE_PREPARED_NETWORK_GATE_CLOSED")
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item)
            self.assertEqual(sha256_file(path), item["sha256"], item)
        sec = data["state_amendments"]["P1_SEC_IAPD"]
        self.assertEqual(sec["availability_resolved"], 113)
        self.assertEqual(sec["captured"], 57)
        self.assertEqual(sec["owner_accepted_labels"], 42)
        self.assertEqual(sec["cdx_target_rows"], 1)
        self.assertFalse(sec["cdx_network_executed"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
