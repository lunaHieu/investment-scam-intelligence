import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_sec_edgar_iapd_primary_review_packet_v1 import build
from scripts.verify_sec_edgar_iapd_manual_group_review_v1 import verify as verify_group
from scripts.verify_sec_edgar_iapd_primary_review_v1 import verify
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file
from tests import test_sec_edgar_iapd_manual_group_review_v1 as group_helpers


AVAILABILITY_PLAN = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\sec_edgar_iapd_all_filer_wayback_availability_plan_v1\availability_plan_v1.jsonl")
OFFLINE_REVIEW = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\sec_edgar_iapd_all_filer_offline_review_v1\offline_review_records_v1.jsonl")
IAPD = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\legitimate_iapd_normalized_v1.jsonl")


class SecEdgarIapdPrimaryReviewV1Tests(unittest.TestCase):
    def make_packet(self, directory: Path) -> Path:
        helper = group_helpers.SecEdgarIapdManualGroupReviewV1Tests()
        group_packet_path, _ = helper.make_packet(directory)
        group_review = helper.make_review(group_packet_path)
        group_review_path = directory / "manual_group_review.json"
        group_review_path.write_text(json.dumps(group_review, indent=2) + "\n", encoding="utf-8")
        group_qa = verify_group(group_packet_path, group_review_path)
        group_qa_path = directory / "manual_group_review_qa.json"
        group_qa_path.write_text(json.dumps(group_qa, indent=2) + "\n", encoding="utf-8")
        group_packet = load_object(group_packet_path)
        manifest_path = Path(group_packet["inputs"]["exact_text_manifest"]["path"])
        packet = build(
            group_packet_path=group_packet_path,
            group_review_path=group_review_path,
            group_qa_path=group_qa_path,
            manifest_path=manifest_path,
            availability_plan_path=AVAILABILITY_PLAN,
            offline_review_path=OFFLINE_REVIEW,
            iapd_path=IAPD,
        )
        packet_path = directory / "primary_packet.json"
        packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return packet_path

    def make_review(self, packet_path: Path) -> dict:
        packet = load_object(packet_path)
        rows = []
        for source in packet["records"]:
            rows.append({
                "record_id": source["record_id"],
                "primary_recommendation": "LEGITIMATE",
                "assessments": {"identity_linkage": "PASS", "task_relevance": "PASS", "capture_chronology": "PASS", "repurpose_or_parking": "PASS", "contradiction_screen": "PASS"},
                "supporting_facts": ["The captured page names the adviser identity and describes investment services.", "The frozen IAPD record supplies the same candidate host and compatible entity evidence."],
                "uncertainty_reasons": [],
                "rationale": "The locally captured artifact independently aligns with the frozen adviser identity, host, and investment-service role, while chronology and contradiction checks show no parking, repurpose, or competing operator signal.",
                "ground_truth_status": "UNCERTAIN",
                "label_created": False,
                "training_eligible": "NO",
            })
        return {
            "review_id": "ISI_SEC_EDGAR_IAPD_PRIMARY_REVIEW_V1",
            "status": "PRIMARY_REVIEW_COMPLETE_BLIND_SECOND_REVIEW_REQUIRED",
            "input_packet": {"path": str(packet_path), "sha256": sha256_file(packet_path)},
            "reviewer": {"mode": "AI_ASSISTED_PRIMARY_MANUAL_REVIEW_AUTHORIZED_BY_OWNER", "network_access_used": False, "model_predictions_visible": False, "source_membership_treated_as_ground_truth": False},
            "records": rows,
            "decision": {"blind_second_review_required": True, "ground_truth_labeling_completed": False, "training_allowed": False},
        }

    def test_primary_packet_contains_local_official_evidence_and_review_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            packet_path = self.make_packet(directory)
            packet = load_object(packet_path)
            self.assertEqual(packet["record_count"], 1)
            self.assertIn("iapd", packet["records"][0]["official_evidence"])
            self.assertIn("sec_edgar_iapd_offline_review", packet["records"][0]["official_evidence"])
            review = self.make_review(packet_path)
            review_path = directory / "primary_review.json"
            review_path.write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
            qa = verify(packet_path, review_path)
            self.assertEqual(qa["status"], "PASS_PRIMARY_REVIEW_BLIND_SECOND_REVIEW_MAY_BE_PREPARED")
            self.assertEqual(qa["checks"]["recommendation_counts"], {"LEGITIMATE": 1})
            self.assertEqual(qa["checks"]["labels_created"], 0)

    def test_legitimate_recommendation_fails_if_any_assessment_is_uncertain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            packet_path = self.make_packet(directory)
            review = self.make_review(packet_path)
            review["records"][0]["assessments"]["identity_linkage"] = "UNCERTAIN"
            review_path = directory / "bad_primary_review.json"
            review_path.write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
            qa = verify(packet_path, review_path)
            self.assertEqual(qa["status"], "FAIL")
            self.assertTrue(any("affirmative evidence" in error for error in qa["errors"]))


if __name__ == "__main__":
    unittest.main()
