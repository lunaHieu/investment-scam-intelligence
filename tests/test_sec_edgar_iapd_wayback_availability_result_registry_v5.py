import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_availability_result_v5.json"


class SecEdgarIapdWaybackAvailabilityResultRegistryV5Tests(unittest.TestCase):
    def test_registry_pins_partial_result_and_keeps_capture_closed(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"] + data["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])
        findings = data["findings"]
        self.assertEqual(findings["resolved_result_count"], 107)
        self.assertEqual(findings["available_snapshot_count"], 52)
        self.assertEqual(findings["unavailable_snapshot_count"], 55)
        self.assertEqual(findings["unresolved_error_count"], 8)
        self.assertEqual(findings["external_holdout_unresolved"], 4)
        self.assertEqual(findings["network_request_count_v5"], 23)
        self.assertFalse(findings["stopped_on_http_429"])
        self.assertTrue(data["decision"]["v5_execution_consumed"])
        self.assertFalse(data["decision"]["v5_may_be_reexecuted"])
        self.assertFalse(data["decision"]["capture_plan_construction_allowed"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
