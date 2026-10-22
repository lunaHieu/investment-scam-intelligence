import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_capture_retry_execution_tooling_v2.json"


class SecEdgarIapdWaybackCaptureRetryExecutionRegistryV2Tests(unittest.TestCase):
    def test_registry_pins_policy_compliant_executor_without_network(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])

        findings = data["findings"]
        self.assertTrue(findings["descriptive_user_agent_has_tool_version_and_model"])
        self.assertTrue(findings["retry_after_header_preserved"])
        self.assertEqual(findings["network_operations_at_tooling_freeze"], 0)
        self.assertFalse(data["decision"]["v1_historical_tooling_mutated"])
        self.assertFalse(data["decision"]["network_execution_allowed_now"])


if __name__ == "__main__":
    unittest.main()
