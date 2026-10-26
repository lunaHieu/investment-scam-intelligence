import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]


class ArchiveBottleneckResolutionStateV1Tests(unittest.TestCase):
    def test_reproducibility_v31_hash_chain_and_decision(self) -> None:
        state = json.loads((ROOT / "registry/analyses/reproducibility_current_state_v31.json").read_text(encoding="utf-8"))
        self.assertFalse(state["current_state"]["recovery_lane_blocks_project"])
        self.assertFalse(state["current_state"]["automatic_fixed_24h_retry_chain_allowed"])
        for item in state["implementation"]:
            self.assertEqual(sha256_file(ROOT / item["path"]), item["sha256"])
        self.assertEqual(sha256_file(ROOT / state["supersedes"]["path"]), state["supersedes"]["sha256"])

    def test_ledger_v34_marks_only_recovery_lane_closed(self) -> None:
        ledger = json.loads((ROOT / "registry/analyses/project_state_gap_ledger_v34.json").read_text(encoding="utf-8"))
        self.assertFalse(ledger["state_amendments"]["P1_V11_METADATA_RECOVERY"]["project_blocked"])
        self.assertTrue(ledger["decision"]["independent_project_work_allowed_now"])
        self.assertFalse(ledger["decision"]["new_identical_24h_retry_chain_allowed"])
        for item in ledger["inputs"] + ledger["implementation"]:
            self.assertEqual(sha256_file(ROOT / item["path"]), item["sha256"])


if __name__ == "__main__":
    unittest.main()
