import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_availability_retry_release_v4.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SecEdgarIapdWaybackAvailabilityRetryReleaseRegistryV4Tests(unittest.TestCase):
    def test_registry_pins_24h_cooldown_release_and_keeps_capture_closed(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in registry["inputs"] + registry["implementation"] + registry["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])
        self.assertEqual(registry["findings"]["resolved_rows_preserved"], 84)
        self.assertEqual(registry["findings"]["retry_rows"], 31)
        self.assertEqual(registry["findings"]["minimum_cooldown_seconds"], 86400)
        self.assertEqual(registry["findings"]["minimum_delay_seconds"], 30.0)
        self.assertFalse(registry["decision"]["network_execution_allowed_at_freeze_time"])
        for gate in ("candidate_live_domain_access_allowed", "archived_page_download_allowed", "artifact_capture_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "training_allowed"):
            self.assertFalse(registry["decision"][gate])


if __name__ == "__main__":
    unittest.main()
