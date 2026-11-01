import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "registry/analyses/pbc_offline_diagnostic_harness_v1.json"
REPRO = ROOT / "registry/analyses/reproducibility_current_state_v72.json"
LEDGER = ROOT / "registry/analyses/project_state_gap_ledger_v75.json"


def assert_pins(test: unittest.TestCase, entries: list[dict]) -> None:
    for item in entries:
        path = ROOT / item["path"]
        test.assertTrue(path.is_file(), item["path"])
        test.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])


class PbcOfflineDiagnosticHarnessRegistryV1Tests(unittest.TestCase):
    def test_harness_registration_pins_code_and_closes_execution_gates(self):
        data = json.loads(ANALYSIS.read_text(encoding="utf-8"))
        assert_pins(self, data["inputs"] + data["implementation"])
        self.assertEqual(data["status"], "PASS_SYNTHETIC_INTEGRATION_ONLY_NO_EXECUTOR_WIRING")
        self.assertEqual(data["tests"]["passed"], 6)
        self.assertEqual(data["tests"]["current_full_suite"]["passed"], 1185)
        self.assertEqual(data["tests"]["current_full_suite"]["failed"], 0)
        self.assertEqual(data["tests"]["registry_validation"]["analysis_registries"], 405)
        self.assertFalse(data["integration_contract"]["executor_wiring"])
        self.assertFalse(data["decision"]["network_execution_allowed"])
        self.assertFalse(data["decision"]["same_release_retry_allowed"])
        self.assertFalse(data["decision"]["training_allowed"])

    def test_current_reproducibility_and_ledger_pins(self):
        repro = json.loads(REPRO.read_text(encoding="utf-8"))
        assert_pins(self, repro["inputs"] + repro["implementation"] + [repro["output"]])
        self.assertEqual(repro["current_entrypoint"], "registry/analyses/project_state_gap_ledger_v75.json")
        self.assertEqual(repro["quality"]["full_suite_passed"], 1185)
        self.assertEqual(repro["quality"]["analysis_registries"], 405)
        self.assertFalse(repro["decision"]["network_execution_allowed"])

        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        assert_pins(self, ledger["inputs"] + ledger["implementation"])
        self.assertEqual(ledger["state_amendments"]["synthetic_integration_tests_passed"], 6)
        self.assertFalse(ledger["decision"]["new_source_request_authorized"])
        self.assertFalse(ledger["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
