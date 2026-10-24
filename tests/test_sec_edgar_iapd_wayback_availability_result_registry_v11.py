import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_availability_result_v11.json"


class SecEdgarIapdWaybackAvailabilityResultRegistryV11Tests(unittest.TestCase):
    def test_registry_pins_complete_supplemental_result(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"] + data["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])

        findings = data["findings"]
        self.assertEqual(findings["resolved_results"], 115)
        self.assertEqual(findings["available_results"], 60)
        self.assertEqual(findings["unavailable_results"], 55)
        self.assertEqual(findings["unresolved_results"], 0)
        self.assertEqual(findings["network_requests_v11"], 2)
        self.assertFalse(findings["stopped_on_http_429"])
        self.assertTrue(findings["supplemental_availability_complete"])

        decision = data["decision"]
        self.assertTrue(decision["v11_result_registered"])
        self.assertTrue(decision["v11_must_never_be_rerun"])
        self.assertFalse(decision["original_capture_plan_mutation_allowed"])
        self.assertFalse(decision["training_allowed"])


if __name__ == "__main__":
    unittest.main()
