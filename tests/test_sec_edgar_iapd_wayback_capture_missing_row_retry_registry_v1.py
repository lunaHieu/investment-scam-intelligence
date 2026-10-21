import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_capture_missing_row_retry_release_v1.json"


class SecEdgarIapdCaptureMissingRowRetryRegistryV1Tests(unittest.TestCase):
    def test_registry_pins_exact_one_row_future_gated_retry(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for section in ("inputs", "implementation", "outputs"):
            for item in data[section]:
                path = Path(item["path"])
                if not path.is_absolute():
                    path = ROOT / path
                self.assertTrue(path.is_file(), item["role"])
                self.assertEqual(sha256_file(path), item["sha256"], item["role"])
        self.assertEqual(data["result"]["retry_capture_count"], 1)
        self.assertEqual(data["result"]["ordered_retry_ids"], ["TTCV1_EDGAR_AVAIL_DEV_037"])
        self.assertEqual(data["result"]["not_before"], "2026-10-22T23:08:09.711801+07:00")
        self.assertFalse(data["decision"]["network_execution_allowed_now"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
