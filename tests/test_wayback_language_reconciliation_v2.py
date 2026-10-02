import unittest

from scripts.reconcile_wayback_language_benchmark_v2 import reconcile


class WaybackLanguageReconciliationV2Tests(unittest.TestCase):
    def test_keeps_only_balanced_high_confidence_agreements(self):
        packet_items = []
        primary_reviews = []
        mappings = []
        second_reviews = []
        for index, decision in enumerate(("CONFIRMED", "CONFIRMED", "LEGITIMATE"), start=1):
            candidate_id = f"C{index}"
            blind_id = f"B{index}"
            packet_items.append({"candidate_id": candidate_id, "candidate_host": f"{candidate_id}.test", "artifact": {"visible_text": "text", "text_sha256": f"t{index}", "capture_sha256": f"c{index}"}, "official_reference": {}, "official_reference_record": {}})
            primary_reviews.append({"candidate_id": candidate_id, "evidence_decision": decision, "confidence": "HIGH", "language_decision": "ENGLISH", "artifact_text_sha256": f"t{index}", "capture_sha256": f"c{index}"})
            mappings.append({"blind_review_id": blind_id, "candidate_id": candidate_id, "first_review_decision": decision, "artifact_text_sha256": f"t{index}", "capture_sha256": f"c{index}"})
            second_reviews.append({"blind_review_id": blind_id, "decision": decision, "confidence": "HIGH"})
        records, nonagreements, counts = reconcile(
            {"items": packet_items},
            {"review_id": "P", "reviews": primary_reviews},
            mappings,
            {"reviews": second_reviews},
            seed="seed",
        )
        self.assertEqual(counts["matched_per_class"], 1)
        self.assertEqual(len(records), 2)
        self.assertFalse(nonagreements)
        self.assertEqual({row["ground_truth_status"] for row in records}, {"CONFIRMED", "LEGITIMATE"})


if __name__ == "__main__":
    unittest.main()
