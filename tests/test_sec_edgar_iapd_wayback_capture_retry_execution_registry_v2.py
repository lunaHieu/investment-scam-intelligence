import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_capture_retry_execution_tooling_v2_1.json"


class SecEdgarIapdWaybackCaptureRetryExecutionRegistryV2Tests(unittest.TestCase):
    def test_registry_pins_v2_post_execution_compatibility(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])

        findings = data["findings"]
        self.assertTrue(findings["descriptive_user_agent_has_tool_version_and_model"])
        self.assertTrue(findings["retry_after_header_preserved"])
        self.assertTrue(findings["final_output_state_supported_by_tests"])
        self.assertEqual(findings["network_operations_at_tooling_freeze"], 0)
        self.assertTrue(data["decision"]["historical_v2_registry_preserved"])
        self.assertFalse(data["decision"]["v2_runtime_may_be_reexecuted"])


if __name__ == "__main__":
    unittest.main()
