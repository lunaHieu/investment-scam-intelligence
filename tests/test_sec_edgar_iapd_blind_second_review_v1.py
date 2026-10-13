import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_sec_edgar_iapd_blind_second_review_packet_v1 import build
from scripts.verify_sec_edgar_iapd_blind_second_review_v1 import verify
from scripts.verify_sec_edgar_iapd_primary_review_v1 import verify as verify_primary
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file
from tests import test_sec_edgar_iapd_primary_review_v1 as primary_helpers


class SecEdgarIapdBlindSecondReviewV1Tests(unittest.TestCase):
    def make_packet(self, directory: Path) -> Path:
        helper = primary_helpers.SecEdgarIapdPrimaryReviewV1Tests()
        primary_packet_path = helper.make_packet(directory)
        primary_review = helper.make_review(primary_packet_path)
        primary_review_path = directory / "primary_review.json"
        primary_review_path.write_text(json.dumps(primary_review, indent=2) + "\n", encoding="utf-8")
        primary_qa = verify_primary(primary_packet_path, primary_review_path)
        primary_qa_path = directory / "primary_review_qa.json"
        primary_qa_path.write_text(json.dumps(primary_qa, indent=2) + "\n", encoding="utf-8")
        packet = build(primary_packet_path, primary_review_path, primary_qa_path)
        packet_path = directory / "blind_second_packet.json"
        packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return packet_path

    def make_review(self, packet_path: Path) -> dict:
        packet = load_object(packet_path)
        rows = [{
            "record_id": source["record_id"],
            "second_recommendation": "LEGITIMATE",
            "assessments": {"identity_linkage": "PASS", "task_relevance": "PASS", "capture_chronology": "PASS", "repurpose_or_parking": "PASS", "contradiction_screen": "PASS"},
            "supporting_facts": ["The captured page independently identifies the adviser and its investment services.", "The frozen IAPD and EDGAR evidence is compatible with the captured host and identity."],
            "uncertainty_reasons": [],
            "rationale": "The second reviewer independently found consistent captured identity, investment relevance, chronology, and official offline evidence, with no parking, repurpose, contradiction, or competing operator indication.",
            "ground_truth_status": "UNCERTAIN",
            "label_created": False,
            "training_eligible": "NO",
        } for source in packet["records"]]
        return {
            "review_id": "ISI_SEC_EDGAR_IAPD_BLIND_SECOND_REVIEW_V1",
            "status": "BLIND_SECOND_REVIEW_COMPLETE_RECONCILIATION_REQUIRED",
            "input_packet": {"path": str(packet_path), "sha256": sha256_file(packet_path)},
            "reviewer": {"mode": "AI_ASSISTED_BLIND_SECOND_REVIEW_AUTHORIZED_BY_OWNER", "primary_decisions_visible": False, "network_access_used": False, "model_predictions_visible": False, "source_membership_treated_as_ground_truth": False},
            "records": rows,
            "decision": {"reconciliation_required": True, "ground_truth_labeling_completed": False, "training_allowed": False},
        }

    def test_blind_packet_omits_primary_decisions_and_review_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            packet_path = self.make_packet(directory)
            serialized = packet_path.read_text(encoding="utf-8")
            self.assertNotIn('"primary_recommendation":', serialized)
            self.assertNotIn("PRIMARY_REVIEW_COMPLETE", serialized)
            packet = load_object(packet_path)
            self.assertFalse(packet["blinding_contract"]["primary_recommendations_included"])
            review = self.make_review(packet_path)
            review_path = directory / "second_review.json"
            review_path.write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
            qa = verify(packet_path, review_path)
            self.assertEqual(qa["status"], "PASS_BLIND_SECOND_REVIEW_RECONCILIATION_MAY_BE_PREPARED")
            self.assertFalse(qa["checks"]["primary_decisions_visible"])
            self.assertEqual(qa["checks"]["labels_created"], 0)

    def test_second_review_fails_if_primary_decisions_were_visible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            packet_path = self.make_packet(directory)
            review = self.make_review(packet_path)
            review["reviewer"]["primary_decisions_visible"] = True
            review_path = directory / "bad_second_review.json"
            review_path.write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
            qa = verify(packet_path, review_path)
            self.assertEqual(qa["status"], "FAIL")
            self.assertTrue(any("firewall" in error for error in qa["errors"]))


if __name__ == "__main__":
    unittest.main()
