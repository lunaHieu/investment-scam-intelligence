import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_all_filer_wayback_availability_plan_v1.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SecEdgarIapdAllFilerWaybackAvailabilityPlanRegistryV1Tests(unittest.TestCase):
    def test_registry_pins_plan_and_keeps_network_capture_label_model_closed(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(registry["status"], "FROZEN_INDEPENDENTLY_VERIFIED_BOUNDED_DISJOINT_PLAN_NETWORK_CLOSED")
        for item in registry["inputs"] + registry["implementation"] + registry["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])
        self.assertEqual(registry["findings"]["plan_rows"], 115)
        self.assertEqual(registry["findings"]["development_rows"], 91)
        self.assertEqual(registry["findings"]["external_holdout_rows"], 24)
        self.assertEqual(registry["findings"]["excluded_identity_caution_rows"], 19)
        self.assertEqual(registry["findings"]["network_requests_executed"], 0)
        for gate in ("wayback_availability_query_execution_allowed", "candidate_live_domain_access_allowed", "archived_page_download_allowed", "artifact_capture_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "training_allowed"):
            self.assertFalse(registry["decision"][gate])


if __name__ == "__main__":
    unittest.main()
