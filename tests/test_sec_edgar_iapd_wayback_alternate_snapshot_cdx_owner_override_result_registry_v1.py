import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_alternate_snapshot_cdx_owner_override_result_v1.json"


class AlternateSnapshotCdxOwnerOverrideResultRegistryV1Tests(unittest.TestCase):
    def test_registry_pins_canonical_empty_response_and_closes_a1(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for section in ("inputs", "implementation", "outputs"):
            for item in data[section]:
                path = Path(item["path"])
                if not path.is_absolute():
                    path = ROOT / path
                self.assertTrue(path.is_file(), item["role"])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["role"])
        self.assertEqual(data["result"]["network_request_count"], 1)
        self.assertEqual(data["result"]["http_status"], 200)
        self.assertEqual(data["result"]["response_bytes"], 3)
        self.assertTrue(data["decision"]["a1_complete"])
        self.assertFalse(data["decision"]["same_query_retry_allowed"])
        self.assertTrue(data["decision"]["quarantine_remains"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
