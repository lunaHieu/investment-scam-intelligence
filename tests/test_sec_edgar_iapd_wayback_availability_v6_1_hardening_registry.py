import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = (
    ROOT
    / "registry"
    / "analyses"
    / "sec_edgar_iapd_wayback_availability_v6_1_execution_hardening.json"
)


class SecEdgarIapdWaybackAvailabilityV61HardeningRegistryTests(unittest.TestCase):
    def test_amendment_pins_authoritative_executor_and_keeps_gates_closed(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"])
        self.assertEqual(
            data["decision"]["authoritative_execution_module"],
            "scripts.retry_sec_edgar_iapd_wayback_availability_v6_1",
        )
        self.assertTrue(data["decision"]["legacy_v6_executor_superseded_for_execution_only"])
        self.assertTrue(data["decision"]["frozen_v6_config_retained"])
        self.assertTrue(data["decision"]["v6_result_verifier_retained"])
        self.assertFalse(data["decision"]["network_execution_performed"])
        self.assertFalse(data["decision"]["capture_plan_construction_allowed_now"])
        self.assertFalse(data["decision"]["training_allowed"])
        self.assertEqual(data["findings"]["resolved_v5_rows_preserved"], 107)
        self.assertEqual(data["findings"]["unresolved_v6_retry_rows"], 8)
        self.assertEqual(data["findings"]["minimum_delay_seconds"], 60.0)


if __name__ == "__main__":
    unittest.main()
