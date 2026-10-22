import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_capture_retry_execution_tooling_v1_1.json"


class SecEdgarIapdWaybackCaptureRetryExecutionRegistryV1Tests(unittest.TestCase):
    def test_registry_pins_post_execution_compatibility_without_mutating_v1(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["role"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["role"])
        findings = data["findings"]
        self.assertTrue(findings["partial_reserved_before_network"])
        self.assertTrue(findings["below_minimum_response_diagnostics_preserved"])
        self.assertTrue(findings["completed_57_byte_hashes_preflighted"])
        self.assertTrue(findings["final_output_state_supported_by_tests"])
        self.assertTrue(data["decision"]["historical_v1_registry_preserved"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
