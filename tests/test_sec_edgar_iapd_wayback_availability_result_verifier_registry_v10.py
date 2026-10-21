import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_availability_result_verifier_v10.json"


class SecEdgarIapdWaybackAvailabilityResultVerifierRegistryV10Tests(unittest.TestCase):
    def test_registry_pins_predeclared_verifier_without_mutating_v5_capture(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])

        findings = data["findings"]
        self.assertEqual(findings["resolved_parent_rows_to_preserve"], 113)
        self.assertEqual(findings["retry_population_limit"], 2)
        self.assertEqual(findings["maximum_redirects"], 3)

        decision = data["decision"]
        self.assertTrue(decision["capture_release_v5_preserved"])
        self.assertFalse(decision["v10_result_may_mutate_capture_v5"])
        self.assertFalse(decision["training_allowed"])


if __name__ == "__main__":
    unittest.main()
