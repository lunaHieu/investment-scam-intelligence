import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = (
    ROOT
    / "registry"
    / "analyses"
    / "sec_edgar_iapd_wayback_capture_retry_tooling_v1.json"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SecEdgarIapdWaybackCaptureRetryToolingRegistryV1Tests(unittest.TestCase):
    def test_registry_hashes_and_gates(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])
        self.assertEqual(data["outputs"], [])
        self.assertTrue(data["findings"]["actual_v1_partial_qa_hash_only_schema_supported"])
        self.assertTrue(data["findings"]["capture_plan_resolved_only_from_source_release"])
        self.assertTrue(data["findings"]["full_capture_result_qa_recomputed_and_required_equal"])
        self.assertTrue(data["findings"]["exact_missing_or_error_rows_only"])
        self.assertTrue(data["findings"]["completed_bytes_and_hashes_preserved"])
        self.assertEqual(data["findings"]["minimum_cooldown_seconds"], 86400.0)
        self.assertEqual(data["findings"]["maximum_attempts_per_snapshot"], 1)
        self.assertTrue(data["findings"]["stop_on_http_429"])
        self.assertFalse(data["decision"]["concrete_retry_release_created"])
        self.assertFalse(data["decision"]["network_execution_allowed_now"])
        self.assertFalse(data["decision"]["training_allowed"])
        self.assertEqual(data["safety_contract"]["network_operations"], 0)


if __name__ == "__main__":
    unittest.main()
