import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_availability_result_verifier_v6.json"


class SecEdgarIapdWaybackAvailabilityResultVerifierRegistryV6Tests(unittest.TestCase):
    def test_registry_pins_predeclared_verifier_and_keeps_all_gates_closed(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])
        self.assertEqual(data["findings"]["resolved_parent_rows_to_preserve"], 107)
        self.assertEqual(data["findings"]["retry_population_limit"], 8)
        self.assertEqual(data["findings"]["complete_result_requires_unresolved_rows"], 0)
        self.assertFalse(data["decision"]["capture_plan_construction_allowed_now"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
