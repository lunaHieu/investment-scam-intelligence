import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_alternate_snapshot_cdx_owner_override_v1.json"


class AlternateSnapshotCdxOwnerOverrideRegistryV1Tests(unittest.TestCase):
    def test_registry_hashes_and_timing_only_scope(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for section in ("inputs", "implementation", "outputs"):
            for item in data[section]:
                path = Path(item["path"])
                if not path.is_absolute():
                    path = ROOT / path
                self.assertTrue(path.is_file(), item["role"])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["role"])
        self.assertEqual(data["result"]["override_scope"], "NOT_BEFORE_ONLY")
        self.assertEqual(data["result"]["maximum_logical_requests"], 1)
        self.assertFalse(data["decision"]["network_executed"])
        self.assertFalse(data["decision"]["archived_page_download_allowed"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
