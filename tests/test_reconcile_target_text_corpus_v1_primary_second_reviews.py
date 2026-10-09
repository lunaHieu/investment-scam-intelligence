import unittest
from pathlib import Path

from scripts.reconcile_target_text_corpus_v1_primary_second_reviews import reconcile


ROOT = Path(__file__).resolve().parents[1]


class TargetTextCorpusPrimarySecondReconciliationTests(unittest.TestCase):
    def test_reconciliation_recomputes_unique_registration_keys_and_closed_gates(self) -> None:
        result = reconcile(ROOT / "configs" / "target_text_corpus_v1_reconciliation_v1.json")
        self.assertEqual(result["registration_identity_audit"]["duplicate_composite_keys"], 0)
        self.assertEqual(result["summary"]["agreements"], 20)
        self.assertEqual(result["summary"]["disagreements"], 2)
        self.assertEqual(result["summary"]["reconciled_recommendation_counts"], {"CONFIRMED": 4, "LEGITIMATE": 11, "UNCERTAIN": 7})
        self.assertTrue(all(row["ground_truth_status"] == "UNCERTAIN" and row["training_eligible"] == "NO" for row in result["records"]))


if __name__ == "__main__":
    unittest.main()
