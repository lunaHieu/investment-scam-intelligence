import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_capture_retry_result_v1.json"


class SecEdgarIapdWaybackCaptureRetryResultRegistryV1Tests(unittest.TestCase):
    def test_registry_pins_repeat_42_byte_failure_and_quarantine(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"] + data["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])

        result = data["result"]
        self.assertEqual(result["retry_rows"], 1)
        self.assertEqual(result["http_status"], 200)
        self.assertEqual(result["response_bytes"], 42)
        self.assertFalse(result["stopped_on_http_429"])
        self.assertTrue(result["repeat_below_minimum_failure"])
        self.assertTrue(data["decision"]["quarantine_remains"])
        self.assertFalse(data["decision"]["another_same_snapshot_retry_allowed"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
