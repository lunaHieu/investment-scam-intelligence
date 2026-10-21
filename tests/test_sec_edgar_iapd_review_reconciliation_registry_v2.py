import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_review_reconciliation_v2.json"


class SecEdgarIapdReviewReconciliationRegistryV2Tests(unittest.TestCase):
    def test_registry_pins_blinding_reconciliation_and_closed_owner_gate(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "PASS_RECONCILED_42_LEGITIMATE_14_UNCERTAIN_OWNER_ACCEPTANCE_REQUIRED")
        for section in ("inputs", "implementation", "outputs"):
            for item in data[section]:
                path = Path(item["path"])
                if not path.is_absolute():
                    path = ROOT / path
                self.assertTrue(path.is_file(), item["role"])
                self.assertEqual(sha256_file(path), item["sha256"], item["role"])
        result = data["result"]
        self.assertEqual(result["primary_recommendation_counts"], {"LEGITIMATE": 47, "UNCERTAIN": 9})
        self.assertEqual(result["blind_second_recommendation_counts"], {"LEGITIMATE": 44, "UNCERTAIN": 12})
        self.assertEqual(result["reconciled_recommendation_counts"], {"LEGITIMATE": 42, "UNCERTAIN": 14})
        self.assertEqual(result["review_disagreements"], 7)
        self.assertEqual(result["owner_acceptance_pending"], 56)
        self.assertEqual(result["labels_created"], 0)
        self.assertTrue(data["decision"]["owner_acceptance_required"])
        self.assertFalse(data["decision"]["label_materialization_allowed_now"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
