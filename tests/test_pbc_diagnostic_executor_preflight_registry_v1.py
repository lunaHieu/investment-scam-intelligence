import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "registry/analyses/pbc_diagnostic_executor_preflight_v1.json"
REPRO = ROOT / "registry/analyses/reproducibility_current_state_v73.json"
LEDGER = ROOT / "registry/analyses/project_state_gap_ledger_v76.json"


def assert_pins(test: unittest.TestCase, entries: list[dict]) -> None:
    for item in entries:
        path = ROOT / item["path"]
        test.assertTrue(path.is_file(), item["path"])
        test.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])


class PbcDiagnosticExecutorPreflightRegistryV1Tests(unittest.TestCase):
    def test_preflight_registration_pins_tooling_and_keeps_execution_closed(self):
        data = json.loads(ANALYSIS.read_text(encoding="utf-8"))
        assert_pins(self, data["inputs"] + data["implementation"])
        self.assertEqual(data["status"], "PASS_SYNTHETIC_CANDIDATE_GATE_CHECKED_EXECUTION_ALWAYS_CLOSED")
        self.assertEqual(data["tests"]["focused_preflight_tests_passed"], 10)
        self.assertFalse(data["decision"]["network_execution_allowed"])
        self.assertFalse(data["decision"]["actual_release_created"])
        self.assertEqual(data["safety_contract"]["network_operations"], 0)
        self.assertEqual(data["safety_contract"]["labels_created"], 0)

    def test_current_reproducibility_and_gap_ledger_are_hash_pinned(self):
        repro = json.loads(REPRO.read_text(encoding="utf-8"))
        assert_pins(self, repro["inputs"] + repro["implementation"] + [repro["output"]])
        self.assertEqual(repro["current_entrypoint"], "registry/analyses/project_state_gap_ledger_v76.json")
        self.assertEqual(repro["quality"]["full_suite_passed"], 1197)
        self.assertEqual(repro["quality"]["analysis_registries"], 408)
        self.assertFalse(repro["decision"]["network_execution_allowed"])

        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        assert_pins(self, ledger["inputs"] + ledger["implementation"])
        self.assertEqual(ledger["state_amendments"]["synthetic_preflight_tests_passed"], 10)
        self.assertFalse(ledger["state_amendments"]["actual_release_created"])
        self.assertFalse(ledger["decision"]["new_source_request_authorized"])
        self.assertFalse(ledger["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
