import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_availability_retry_release_v6.json"


class SecEdgarIapdWaybackAvailabilityRetryReleaseRegistryV6Tests(unittest.TestCase):
    def test_registry_pins_release_and_keeps_capture_closed(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"] + data["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])
        self.assertEqual(data["findings"]["resolved_rows_preserved"], 107)
        self.assertEqual(data["findings"]["retry_rows"], 8)
        self.assertEqual(data["findings"]["minimum_cooldown_seconds"], 86400)
        self.assertEqual(data["findings"]["minimum_delay_seconds"], 60.0)
        self.assertFalse(data["decision"]["network_execution_allowed_at_freeze_time"])
        self.assertFalse(data["decision"]["capture_plan_construction_allowed_now"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
