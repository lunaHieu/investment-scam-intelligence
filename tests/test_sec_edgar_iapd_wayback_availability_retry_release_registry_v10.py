import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_availability_retry_release_v10.json"


class SecEdgarIapdWaybackAvailabilityRetryReleaseRegistryV10Tests(unittest.TestCase):
    def test_registry_pins_two_row_retry_and_preserves_v5_capture(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"] + data["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])

        findings = data["findings"]
        self.assertEqual(findings["resolved_rows_preserved"], 113)
        self.assertEqual(findings["retry_rows"], 2)
        self.assertEqual(findings["minimum_delay_seconds"], 60.0)
        self.assertEqual(findings["not_before"], "2026-10-22T18:18:58.983066+07:00")
        self.assertEqual(findings["independent_release_qa_status"], "PASS_FROZEN_NOT_BEFORE_24H_UNRESOLVED_ONLY_CRASH_SAFE_PACING_PRESERVED")
        self.assertEqual(findings["independent_release_qa_sha256"], "43c19b1b8d05eddbfebec2b46a6b5233eb3f611888c752edb42ddc7ea14080a6")
        self.assertTrue(findings["superseded_preformat_qa_preserved"])

        decision = data["decision"]
        self.assertTrue(decision["capture_release_v5_preserved"])
        self.assertFalse(decision["capture_execution_allowed_before_next_run"])
        self.assertFalse(decision["training_allowed"])


if __name__ == "__main__":
    unittest.main()
