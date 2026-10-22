import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_capture_retry_execution_tooling_v1.json"


class SecEdgarIapdWaybackCaptureRetryExecutionRegistryV1Tests(unittest.TestCase):
    def test_registry_pins_retry_executor_and_closed_gate(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["role"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["role"])
        findings = data["findings"]
        self.assertTrue(findings["partial_reserved_before_network"])
        self.assertTrue(findings["below_minimum_response_diagnostics_preserved"])
        self.assertTrue(findings["completed_57_byte_hashes_preflighted"])
        self.assertFalse(data["decision"]["network_execution_allowed_now"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
