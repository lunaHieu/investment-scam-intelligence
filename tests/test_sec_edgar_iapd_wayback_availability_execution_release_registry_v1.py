import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_availability_execution_release_v1.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SecEdgarIapdWaybackAvailabilityExecutionReleaseRegistryV1Tests(unittest.TestCase):
    def test_registry_pins_release_and_opens_only_availability_execution(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in registry["inputs"] + registry["implementation"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])
        self.assertTrue(registry["decision"]["wayback_availability_query_execution_allowed"])
        for gate in ("candidate_live_domain_access_allowed", "archived_page_download_allowed", "artifact_capture_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "training_allowed"):
            self.assertFalse(registry["decision"][gate])
        self.assertEqual(registry["outputs"], [])
        self.assertEqual(registry["findings"]["network_requests_executed_at_release_time"], 0)


if __name__ == "__main__":
    unittest.main()
