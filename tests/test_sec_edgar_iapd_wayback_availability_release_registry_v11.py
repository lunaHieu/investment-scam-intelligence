import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_availability_release_v11.json"


class AvailabilityReleaseRegistryV11Tests(unittest.TestCase):
    def test_registry_hashes_population_and_closed_gate(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for section in ("inputs", "implementation", "outputs"):
            for item in data[section]:
                path = Path(item["path"])
                if not path.is_absolute():
                    path = ROOT / path
                self.assertTrue(path.is_file(), item["role"])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["role"])
        self.assertEqual(data["result"]["ordered_retry_ids"], [
            "TTCV1_EDGAR_AVAIL_HOLDOUT_011",
            "TTCV1_EDGAR_AVAIL_HOLDOUT_018",
        ])
        self.assertEqual(data["result"]["not_before"], "2026-10-24T21:39:37.725131+07:00")
        self.assertFalse(data["decision"]["network_execution_allowed_at_registration"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
