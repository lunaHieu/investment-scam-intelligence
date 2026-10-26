import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]


class B5V2CurrentStateTests(unittest.TestCase):
    def test_reproducibility_v32_hashes_and_gate(self) -> None:
        value = json.loads((ROOT / "registry/analyses/reproducibility_current_state_v32.json").read_text(encoding="utf-8"))
        self.assertTrue(value["current_state"]["b5_gate_open"])
        self.assertEqual(value["current_state"]["b5_network_requests"], 0)
        self.assertFalse(value["current_state"]["a1_rate_limit"])
        self.assertEqual(sha256_file(ROOT / value["supersedes"]["path"]), value["supersedes"]["sha256"])
        for item in value["implementation"]:
            self.assertEqual(sha256_file(ROOT / item["path"]), item["sha256"])

    def test_ledger_v35_is_nonblocking_and_hash_bound(self) -> None:
        value = json.loads((ROOT / "registry/analyses/project_state_gap_ledger_v35.json").read_text(encoding="utf-8"))
        self.assertTrue(value["decision"]["b5_execution_allowed_now"])
        self.assertFalse(value["state_amendments"]["A1_COORDINATION"]["blocks_b5"])
        self.assertFalse(value["state_amendments"]["V11_METADATA_RECOVERY"]["blocks_project"])
        for item in value["inputs"] + value["implementation"]:
            self.assertEqual(sha256_file(ROOT / item["path"]), item["sha256"])


if __name__ == "__main__":
    unittest.main()
