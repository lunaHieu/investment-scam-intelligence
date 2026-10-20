import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_availability_result_v8.json"


class SecEdgarIapdWaybackAvailabilityResultRegistryV8Tests(unittest.TestCase):
    def test_registry_pins_partial_result_and_keeps_capture_closed(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"] + data["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])
        self.assertEqual(data["findings"]["resolved_results"], 113)
        self.assertEqual(data["findings"]["unresolved_results"], 2)
        self.assertEqual(data["findings"]["network_requests_v8"], 2)
        self.assertTrue(data["findings"]["stopped_on_http_429"])
        self.assertFalse(data["decision"]["capture_plan_construction_allowed_now"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
