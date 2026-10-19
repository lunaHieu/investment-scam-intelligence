import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_availability_retry_release_v8.json"


class SecEdgarIapdWaybackAvailabilityRetryReleaseRegistryV8Tests(unittest.TestCase):
    def test_registry_pins_crash_safe_release_and_keeps_capture_closed(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"] + data["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])
        self.assertEqual(data["findings"]["resolved_rows_preserved"], 113)
        self.assertEqual(data["findings"]["retry_rows"], 2)
        self.assertEqual(data["findings"]["unresolved_cohort_counts"], {"DEVELOPMENT": 0, "EXTERNAL_HOLDOUT": 2})
        self.assertEqual(data["findings"]["minimum_delay_seconds"], 60.0)
        self.assertTrue(data["findings"]["crash_safe_executor"])
        self.assertEqual(
            data["findings"]["independent_release_qa_status"],
            "PASS_FROZEN_NOT_BEFORE_24H_UNRESOLVED_ONLY_CRASH_SAFE_PACING_PRESERVED",
        )
        self.assertEqual(
            data["findings"]["independent_release_qa_sha256"],
            "a0b329f726dd06ceab5eea1271c7825aa8b2220592d739756e9fbd2d5dd75c4f",
        )
        self.assertFalse(data["decision"]["network_execution_allowed_at_freeze_time"])
        self.assertFalse(data["decision"]["capture_plan_construction_allowed_now"])
        self.assertFalse(data["decision"]["capture_tooling_v4_supports_v8"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
