import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "registry/analyses/pbc_safe_diagnostic_contract_v1.json"
REPRO = ROOT / "registry/analyses/reproducibility_current_state_v71.json"
LEDGER = ROOT / "registry/analyses/project_state_gap_ledger_v74.json"


def assert_pins(test: unittest.TestCase, entries: list[dict]) -> None:
    for item in entries:
        path = ROOT / item["path"]
        test.assertTrue(path.is_file(), item["path"])
        test.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])


class PbcSafeDiagnosticContractRegistryV1Tests(unittest.TestCase):
    def test_contract_record_pins_implementation_and_keeps_gates_closed(self):
        data = json.loads(ANALYSIS.read_text(encoding="utf-8"))
        assert_pins(self, data["inputs"] + data["implementation"])
        self.assertEqual(data["status"], "PASS_SYNTHETIC_DIAGNOSTICS_ONLY_NOT_EXECUTOR_WIRED")
        self.assertEqual(data["tests"]["passed"], 8)
        self.assertEqual(data["tests"]["current_full_suite"]["passed"], 1177)
        self.assertEqual(data["tests"]["current_full_suite"]["failed"], 0)
        self.assertEqual(data["tests"]["registry_validation"]["analysis_registries"], 402)
        self.assertFalse(data["decision"]["network_execution_allowed"])
        self.assertFalse(data["decision"]["same_release_retry_allowed"])
        self.assertFalse(data["decision"]["training_allowed"])
        self.assertEqual(data["safety_contract"]["network_operations"], 0)
        self.assertEqual(data["safety_contract"]["labels_created"], 0)

    def test_current_reproducibility_and_gap_ledger_are_hash_pinned(self):
        repro = json.loads(REPRO.read_text(encoding="utf-8"))
        assert_pins(self, repro["inputs"] + repro["implementation"] + [repro["output"]])
        self.assertEqual(repro["current_entrypoint"], "registry/analyses/project_state_gap_ledger_v74.json")
        self.assertFalse(repro["decision"]["network_execution_allowed"])

        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        assert_pins(self, ledger["inputs"] + ledger["implementation"])
        self.assertFalse(ledger["decision"]["new_source_request_authorized"])
        self.assertEqual(ledger["state_amendments"]["synthetic_tests_passed"], 8)


if __name__ == "__main__":
    unittest.main()
