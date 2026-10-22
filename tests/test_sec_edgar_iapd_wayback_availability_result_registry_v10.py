import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_availability_result_v10.json"


class SecEdgarIapdWaybackAvailabilityResultRegistryV10Tests(unittest.TestCase):
    def test_registry_pins_partial_result_without_mutating_completed_work(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"] + data["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])

        findings = data["findings"]
        self.assertEqual(findings["resolved_results"], 113)
        self.assertEqual(findings["available_results"], 58)
        self.assertEqual(findings["unresolved_results"], 2)
        self.assertEqual(findings["network_requests_v10"], 1)
        self.assertEqual(findings["cumulative_network_requests"], 168)
        self.assertTrue(findings["stopped_on_http_429"])

        decision = data["decision"]
        self.assertTrue(decision["completed_capture_and_review_preserved"])
        self.assertFalse(decision["capture_retry_executed_in_same_run"])
        self.assertFalse(decision["training_allowed"])


if __name__ == "__main__":
    unittest.main()
