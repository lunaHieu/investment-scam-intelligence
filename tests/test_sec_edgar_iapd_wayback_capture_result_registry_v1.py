import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_capture_result_v1.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SecEdgarIapdWaybackCaptureResultRegistryV1Tests(unittest.TestCase):
    def test_registry_pins_partial_result_and_bounds_one_failure(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])

        result = data["result"]
        self.assertEqual(result["planned_capture_count"], 58)
        self.assertEqual(result["captured_count"], 57)
        self.assertEqual(result["captured_by_cohort"], {"DEVELOPMENT": 45, "EXTERNAL_HOLDOUT": 12})
        self.assertEqual(result["failed_count"], 1)
        self.assertFalse(result["stopped_on_http_429"])
        self.assertTrue(result["raw_byte_hashes_independently_verified"])

        failure = data["quarantined_failure"]
        self.assertEqual(failure["availability_plan_id"], "TTCV1_EDGAR_AVAIL_DEV_037")
        self.assertEqual(failure["candidate_host"], "lionpoint.com")
        self.assertIsNone(failure["underlying_wayback_cause"])
        self.assertFalse(failure["raw_target_written"])
        self.assertFalse(failure["label_inferred"])

        self.assertFalse(data["decision"]["text_extraction_allowed_by_this_registry_alone"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
