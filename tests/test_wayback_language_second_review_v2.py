import unittest

from scripts.prepare_wayback_language_second_review_v2 import build_blind_packet


class WaybackLanguageSecondReviewV2Tests(unittest.TestCase):
    def test_packet_is_balanced_and_hides_primary_fields(self):
        items = []
        reviews = []
        for candidate_id, decision in (("C1", "CONFIRMED"), ("C2", "CONFIRMED"), ("L1", "LEGITIMATE")):
            items.append({"candidate_id": candidate_id, "candidate_host": candidate_id.lower()+".test", "capture_stratum": "WAYBACK_ARCHIVED_HOMEPAGE_HTML", "artifact": {"visible_text": "text", "text_sha256": candidate_id+"t", "capture_sha256": candidate_id+"c"}, "official_reference": {}, "official_reference_record": {"observed_hosts": [candidate_id.lower()+".test"]}, "entity_name_keys": [candidate_id.lower()]})
            reviews.append({"candidate_id": candidate_id, "evidence_decision": decision, "confidence": "HIGH", "language_decision": "ENGLISH", "artifact_text_sha256": candidate_id+"t", "capture_sha256": candidate_id+"c"})
        packet, mapping, counts = build_blind_packet({"items": items}, {"reviews": reviews}, seed="s")
        self.assertEqual(counts["selected_per_class"], 1)
        self.assertEqual(len(packet["items"]), 2)
        self.assertEqual(len(mapping), 2)
        for item in packet["items"]:
            self.assertNotIn("candidate_id", item)
            self.assertNotIn("first_review_decision", item)
            self.assertNotIn("reference_branch", item)


if __name__ == "__main__":
    unittest.main()
