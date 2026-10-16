import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_capture_plan_tooling_v2.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SecEdgarIapdWaybackCapturePlanToolingRegistryV2Tests(unittest.TestCase):
    def test_registry_pins_generation_aware_tooling_and_keeps_download_closed(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in registry["inputs"] + registry["implementation"]:
            path = ROOT / item["path"]
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])
        self.assertEqual(registry["findings"]["supported_availability_generations"], ["v3", "v4", "v5"])
        self.assertEqual(registry["findings"]["expected_availability_population"], 115)
        self.assertEqual(registry["findings"]["selection_rule"], "ALL_AND_ONLY_AVAILABLE_ROWS_IN_ORIGINAL_ORDER")
        self.assertTrue(registry["decision"]["tooling_ready_before_v5_result"])
        self.assertFalse(registry["decision"]["capture_plan_construction_allowed_now"])
        self.assertFalse(registry["decision"]["archived_page_download_allowed"])
        self.assertFalse(registry["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
