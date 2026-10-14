import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_availability_result_v3.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SecEdgarIapdWaybackAvailabilityResultRegistryV3Tests(unittest.TestCase):
    def test_registry_pins_verified_partial_v3_and_keeps_capture_closed(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in registry["inputs"] + registry["implementation"] + registry["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])
        self.assertEqual(registry["findings"]["available_snapshot_count"], 42)
        self.assertEqual(registry["findings"]["unavailable_snapshot_count"], 42)
        self.assertEqual(registry["findings"]["unresolved_error_count"], 31)
        self.assertEqual(registry["findings"]["external_holdout_unresolved"], 10)
        self.assertFalse(registry["decision"]["capture_plan_construction_allowed"])
        self.assertFalse(registry["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
