import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "project_state_gap_ledger_v19.json"


class ProjectStateGapLedgerV19Tests(unittest.TestCase):
    def test_b1_is_current_without_opening_capture_or_models(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item)
            self.assertEqual(sha256_file(path), item["sha256"], item)
        b1 = data["state_amendments"]["P2_B1_READY_CHANNEL_ENUMERATION"]
        self.assertEqual(b1["planned_candidates"], 70)
        self.assertEqual(b1["candidates_selected"], 0)
        self.assertTrue(b1["b2_queue_materialization_allowed"])
        self.assertFalse(data["decision"]["capture_allowed"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
