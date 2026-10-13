import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_availability_retry_release_v2.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SecEdgarIapdWaybackAvailabilityRetryReleaseRegistryV2Tests(unittest.TestCase):
    def test_registry_pins_retry_and_keeps_nonavailability_gates_closed(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in registry["inputs"] + registry["implementation"]:
            path = ROOT / item["path"]
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])
        self.assertTrue(registry["decision"]["unresolved_only_retry_allowed"])
        self.assertEqual(registry["findings"]["retry_rows"], 70)
        for gate in ("candidate_live_domain_access_allowed", "archived_page_download_allowed", "artifact_capture_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "training_allowed"):
            self.assertFalse(registry["decision"][gate])


if __name__ == "__main__":
    unittest.main()
