import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "registry" / "analyses" / "reproducibility_current_state_v44.json"
LEDGER = ROOT / "registry" / "analyses" / "project_state_gap_ledger_v47.json"


def assert_hashes(test: unittest.TestCase, value: dict) -> None:
    for item in value.get("inputs", []) + value.get("implementation", []):
        path = ROOT / item["path"]
        test.assertTrue(path.is_file(), item["path"])
        test.assertEqual(sha256_file(path), item["sha256"], item["path"])


class CurrentNavigationV44Tests(unittest.TestCase):
    def test_state_and_ledger_hash_chains_reproduce(self) -> None:
        state = json.loads(STATE.read_text(encoding="utf-8"))
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        assert_hashes(self, state)
        assert_hashes(self, ledger)
        self.assertEqual(state["current_state"]["continuation_v2"]["rows"], 48)
        self.assertEqual(ledger["state_amendments"]["CONTINUATION_V2"]["rows"], 48)
        self.assertFalse(ledger["state_amendments"]["CONTINUATION_V2"]["executed"])
        self.assertEqual(state["current_state"]["continuation_v1"]["not_attempted"], 48)

    def test_research_and_network_gates_remain_closed(self) -> None:
        state = json.loads(STATE.read_text(encoding="utf-8"))
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        self.assertEqual(state["current_state"]["data_sufficiency"]["fresh_v1_core_admitted_groups"], 0)
        self.assertEqual(ledger["state_amendments"]["RESEARCH_GAPS"]["conditional_supply"], 42)
        for value in (state["decision"], ledger["decision"]):
            self.assertFalse(value["candidate_live_domain_access_allowed"])
            self.assertFalse(value["training_allowed"])


if __name__ == "__main__":
    unittest.main()
