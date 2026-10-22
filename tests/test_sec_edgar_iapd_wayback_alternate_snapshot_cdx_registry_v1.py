import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = (
    ROOT
    / "registry"
    / "analyses"
    / "sec_edgar_iapd_wayback_alternate_snapshot_cdx_release_v1.json"
)


class AlternateSnapshotCdxRegistryV1Tests(unittest.TestCase):
    def test_registry_hashes_and_closed_gates(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "FROZEN_OFFLINE_PREPARED_INDEPENDENT_QA_PASS")
        for item in data["inputs"] + data["implementation"]:
            path = Path(item["path"]) if item.get("absolute", False) else ROOT / item["path"]
            self.assertTrue(path.is_file(), item)
            self.assertEqual(sha256_file(path), item["sha256"], item)
        result = data["result"]
        self.assertEqual(result["target_rows"], 1)
        self.assertEqual(result["target_availability_plan_id"], "TTCV1_EDGAR_AVAIL_DEV_037")
        self.assertEqual(result["excluded_snapshot_timestamps"], ["20260210193325"])
        self.assertEqual(result["maximum_logical_requests"], 1)
        decision = data["decision"]
        self.assertFalse(decision["network_executed"])
        self.assertFalse(decision["capture_authorized"])
        self.assertFalse(decision["training_allowed"])


if __name__ == "__main__":
    unittest.main()
