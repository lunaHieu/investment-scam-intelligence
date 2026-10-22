import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = (
    ROOT
    / "registry"
    / "analyses"
    / "sec_edgar_iapd_wayback_availability_v11_protocol_v1.json"
)


class AvailabilityV11RegistryV1Tests(unittest.TestCase):
    def test_registry_hashes_exact_population_and_closed_network_gate(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "FROZEN_OFFLINE_TOOLING_QA_PASS_RELEASE_REQUIRED")
        for item in data["inputs"] + data["implementation"]:
            path = Path(item["path"]) if item.get("absolute", False) else ROOT / item["path"]
            self.assertTrue(path.is_file(), item)
            self.assertEqual(sha256_file(path), item["sha256"], item)
        result = data["result"]
        self.assertEqual(
            result["ordered_retry_ids"],
            ["TTCV1_EDGAR_AVAIL_HOLDOUT_011", "TTCV1_EDGAR_AVAIL_HOLDOUT_018"],
        )
        self.assertEqual(result["retry_cohort"], "EXTERNAL_HOLDOUT")
        self.assertEqual(result["resolved_parent_rows_preserved"], 113)
        self.assertFalse(data["decision"]["network_execution_authorized"])
        self.assertTrue(data["decision"]["concrete_release_still_required"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
