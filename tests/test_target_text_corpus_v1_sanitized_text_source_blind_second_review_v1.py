import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_sanitized_text_source_blind_second_review_v1 import PACKET, verify_packet, verify_response


class SanitizedTextSourceBlindSecondReviewV1Tests(unittest.TestCase):
    def test_packet_is_blind_and_bounded(self) -> None:
        self.assertEqual(verify_packet(), {"status":"PASS_BLIND_PACKET_VERIFIED","candidate_count":6})

    def test_response_requires_all_checks_and_preserved_order(self) -> None:
        packet = json.loads(PACKET.read_text(encoding="utf-8"))
        checks = {key:"UNKNOWN" for key in packet["review_contract"]["required_checks"]}
        response = {
            "reviews":[{"candidate_id":item["candidate_id"],"checks":checks,"verdict":"HOLD_FOR_MISSING_EVIDENCE","rationale":"fixture","evidence_urls_reviewed":item["evidence_urls"],"residual_unknowns":["fixture"]} for item in packet["candidates"]],
            "decision":{"acquisition_allowed":False,"training_allowed":False},
            "safety_contract":{"dataset_downloads":0,"candidate_domain_access_operations":0,"raw_html_files_retained":0,"labels_created":0,"model_operations":0}
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "response.json"
            path.write_text(json.dumps(response), encoding="utf-8")
            self.assertEqual(verify_response(path)["candidate_count"], 6)


if __name__ == "__main__":
    unittest.main()
