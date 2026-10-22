import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_owner_acceptance_result_v2.json"


class SecEdgarIapdOwnerAcceptanceRegistryV2Tests(unittest.TestCase):
    def test_registry_pins_owner_acceptance_and_preserves_dataset_gates(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "PASS_OWNER_ACCEPTED_42_LEGITIMATE_14_UNCERTAIN_TRAINING_CLOSED")
        for section in ("inputs", "implementation", "outputs"):
            for item in data[section]:
                path = Path(item["path"])
                if not path.is_absolute():
                    path = ROOT / path
                self.assertTrue(path.is_file(), item["role"])
                self.assertEqual(sha256_file(path), item["sha256"], item["role"])
        result = data["result"]
        self.assertEqual(result["accepted_labels"], 42)
        self.assertEqual(result["uncertain_retained"], 14)
        self.assertEqual(result["accepted_by_cohort"], {"DEVELOPMENT": 33, "EXTERNAL_HOLDOUT": 9})
        self.assertEqual(result["training_eligible_records"], 0)
        self.assertTrue(data["decision"]["capacity_gap_update_may_be_prepared"])
        self.assertFalse(data["decision"]["v1_core_release_ready"])
        self.assertFalse(data["decision"]["training_allowed"])
        self.assertFalse(data["decision"]["model_scoring_allowed"])


if __name__ == "__main__":
    unittest.main()
