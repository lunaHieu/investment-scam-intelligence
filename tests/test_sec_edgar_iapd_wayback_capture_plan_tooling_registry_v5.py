import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_capture_plan_tooling_v5.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SecEdgarIapdWaybackCapturePlanToolingRegistryV5Tests(unittest.TestCase):
    def test_registry_pins_v8_only_tooling_and_keeps_capture_closed(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in registry["implementation"]:
            self.assertEqual(sha256_file(ROOT / item["path"]), item["sha256"], item["path"])
        findings = registry["findings"]
        self.assertEqual(findings["supported_availability_generations"], ["v8"])
        self.assertEqual(findings["expected_availability_population"], 115)
        self.assertTrue(findings["full_population_recomputed"])
        self.assertEqual(findings["selection_rule"], "ALL_RESOLVED_AVAILABLE_ROWS_IN_ORIGINAL_ORDER")
        self.assertTrue(findings["unresolved_rows_quarantined_in_original_order"])
        self.assertTrue(findings["cohort_identity_preserved"])
        self.assertFalse(registry["decision"]["capture_plan_construction_allowed_now"])
        self.assertFalse(registry["decision"]["archived_page_download_allowed"])
        self.assertFalse(registry["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
