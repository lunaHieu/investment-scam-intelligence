import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_availability_result_verifier_v3.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SecEdgarIapdWaybackAvailabilityResultVerifierRegistryV3Tests(unittest.TestCase):
    def test_registry_pins_predeclared_verifier_and_keeps_capture_closed(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in registry["inputs"] + registry["implementation"]:
            path = ROOT / item["path"]
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])
        self.assertEqual(registry["findings"]["expected_plan_rows"], 115)
        self.assertEqual(registry["findings"]["resolved_parent_rows_to_preserve"], 45)
        self.assertEqual(registry["findings"]["retry_population_limit"], 70)
        self.assertTrue(registry["decision"]["verifier_ready_before_result"])
        self.assertFalse(registry["decision"]["network_execution_allowed_by_this_registry"])
        self.assertFalse(registry["decision"]["capture_plan_construction_allowed_now"])
        self.assertFalse(registry["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
