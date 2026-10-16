import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_capture_execution_tooling_v2.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SecEdgarIapdWaybackCaptureExecutionToolingRegistryV2Tests(unittest.TestCase):
    def test_registry_pins_24h_release_tooling_and_keeps_network_closed(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in registry["inputs"] + registry["implementation"]:
            path = ROOT / item["path"]
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])
        self.assertEqual(registry["findings"]["minimum_availability_to_capture_cooldown_seconds"], 86400)
        self.assertEqual(registry["findings"]["minimum_delay_seconds"], 30.0)
        self.assertEqual(registry["findings"]["maximum_attempts_per_snapshot"], 1)
        self.assertTrue(registry["findings"]["raw_byte_hash_verification_required"])
        self.assertFalse(registry["decision"]["network_execution_allowed_now"])
        self.assertFalse(registry["decision"]["text_extraction_allowed_now"])
        self.assertFalse(registry["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
