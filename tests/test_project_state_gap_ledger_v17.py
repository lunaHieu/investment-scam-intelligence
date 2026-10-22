import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "project_state_gap_ledger_v17.json"


class ProjectStateGapLedgerV17Tests(unittest.TestCase):
    def test_current_ledger_registers_a3_without_mutating_a1_a2(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "FROZEN_A3_CAPACITY_MATRIX_A1_A2_GATES_UNCHANGED")
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item)
            self.assertEqual(sha256_file(path), item["sha256"], item)

        sec = data["state_amendments"]["P1_SEC_IAPD"]
        self.assertTrue(sec["a1_cdx_concrete_release_frozen"])
        self.assertFalse(sec["a1_cdx_network_executed"])
        self.assertTrue(sec["a2_v11_tooling_frozen"])
        self.assertFalse(sec["a2_v11_concrete_release_created"])

        capacity = data["state_amendments"]["P2_V1_CORE_CAPACITY"]
        self.assertEqual(capacity["required_groups"], 300)
        self.assertEqual(capacity["admitted_groups"], 0)
        self.assertEqual(capacity["conditional_owner_accepted_supply"], 42)
        self.assertEqual(capacity["conditional_residual_gap"], 258)
        self.assertEqual(capacity["crimson_domain_v1_core_credit"], 0)
        self.assertEqual(capacity["usable_image_assets"], 0)
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
