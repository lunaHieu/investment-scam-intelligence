import unittest

from scripts.prepare_wayback_language_primary_review_v2 import build_primary_packet
from scripts.record_wayback_language_primary_review_v2 import REVIEW_TYPE, validate_response


class WaybackLanguagePrimaryReviewV2Tests(unittest.TestCase):
    def test_packet_keeps_branch_out_of_reviewer_item(self):
        queue = [{"candidate_id": "C1", "candidate_host": "example.test", "reference_branch": "CONFIRMED_CANDIDATE", "source_case_id": "S1", "official_reference": {"url": "https://regulator.test/warning"}, "entity_name_keys": ["example"]}]
        screening = [{"candidate_id": "C1", "candidate_host": "example.test", "screening_decision": "REVIEWABLE_OBSERVED_TEXT", "ground_truth_status": "UNCERTAIN", "label_created": False, "capture_stratum": "WAYBACK_ARCHIVED_HOMEPAGE_HTML", "visible_text": "Example investment service", "text_sha256": "a", "capture_path": "x", "capture_sha256": "b", "automatic_language_bucket": "ENGLISH", "automatic_language_hint": "en", "identity_check": {}}]
        packet, mapping = build_primary_packet(queue, screening)
        self.assertNotIn("reference_branch", packet["items"][0])
        self.assertEqual(mapping[0]["reference_branch"], "CONFIRMED_CANDIDATE")

    def test_hash_pinned_reference_must_contain_candidate_host(self):
        queue = [{"candidate_id": "C1", "candidate_host": "example.test", "reference_branch": "CONFIRMED_CANDIDATE", "source_case_id": "S1", "source_id": "reg", "source_record_id": "1", "official_reference": {"url": "https://regulator.test/warning"}, "entity_name_keys": ["example"]}]
        screening = [{"candidate_id": "C1", "candidate_host": "example.test", "screening_decision": "REVIEWABLE_OBSERVED_TEXT", "ground_truth_status": "UNCERTAIN", "label_created": False, "capture_stratum": "WAYBACK_ARCHIVED_HOMEPAGE_HTML", "visible_text": "Example investment service", "text_sha256": "a", "capture_path": "x", "capture_sha256": "b", "automatic_language_bucket": "ENGLISH", "automatic_language_hint": "en", "identity_check": {}}]
        with self.assertRaisesRegex(ValueError, "absent from official reference"):
            build_primary_packet(queue, screening, {("reg", "1"): {"observed_hosts": ["other.test"]}})

    def test_response_must_cover_packet_exactly_once(self):
        packet = {"items": [{"candidate_id": "C1", "artifact": {"text_sha256": "a", "capture_sha256": "b"}, "review_contract": {"allowed_language_decisions": ["ENGLISH"], "allowed_evidence_decisions": ["CONFIRMED"], "allowed_confidence": ["HIGH"]}}]}
        response = {"review_type": REVIEW_TYPE, "reviewer": "OpenAI Codex AI primary reviewer", "reviewed_at": "2026-10-01", "reviews": [{"candidate_id": "C1", "language_decision": "ENGLISH", "evidence_decision": "CONFIRMED", "confidence": "HIGH", "rationale": "Identity and domain align.", "evidence_checks": ["official warning", "archive identity"], "contradictions": []}]}
        self.assertEqual(validate_response(packet, response)[0]["candidate_id"], "C1")


if __name__ == "__main__":
    unittest.main()
