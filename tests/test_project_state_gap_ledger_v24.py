import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "project_state_gap_ledger_v24.json"


class ProjectStateGapLedgerV24Tests(unittest.TestCase):
    def test_c1_is_current_without_opening_external_or_model_gates(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item)
            self.assertEqual(sha256_file(path), item["sha256"], item)
        c1 = data["state_amendments"]["P3_C1_PARALLEL_OFFLINE_WORKSTREAM"]
        self.assertEqual(c1["scope_items"], 5)
        self.assertEqual(c1["follow_on_gates"], 3)
        self.assertEqual(c1["admitted_groups"], 0)
        self.assertEqual(c1["conditional_residual_gap"], 258)
        self.assertEqual(c1["source_files_acquired"], 0)
        self.assertTrue(data["decision"]["c1_complete"])
        self.assertFalse(data["decision"]["network_execution_allowed_now"])
        self.assertFalse(data["decision"]["candidate_enumeration_allowed"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
