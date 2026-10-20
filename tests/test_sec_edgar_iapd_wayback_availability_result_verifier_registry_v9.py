import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_availability_result_verifier_v9.json"


class SecEdgarIapdWaybackAvailabilityResultVerifierRegistryV9Tests(unittest.TestCase):
    def test_registry_pins_predeclared_verifier_and_requires_v9_aware_capture_tooling(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])
        self.assertEqual(data["findings"]["resolved_parent_rows_to_preserve"], 113)
        self.assertEqual(data["findings"]["retry_population_limit"], 2)
        self.assertEqual(data["findings"]["maximum_redirects"], 3)
        self.assertFalse(data["decision"]["capture_plan_construction_allowed_now"])
        self.assertTrue(data["decision"]["v9_aware_capture_tooling_required_after_complete_pass"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
