import json
import tempfile
import unittest
from pathlib import Path

from scripts.analyze_sec_edgar_iapd_post_capture_grouping_v1 import execute as execute_grouping
from scripts.build_sec_edgar_iapd_manual_group_review_packet_v1 import build
from scripts.verify_sec_edgar_iapd_manual_group_review_v1 import AUTOMATED_EXCLUSIONS, verify
from scripts.verify_sec_edgar_iapd_post_capture_grouping_v1 import verify as verify_grouping
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file
from tests import test_sec_edgar_iapd_post_capture_grouping_v1 as grouping_helpers


class SecEdgarIapdManualGroupReviewV1Tests(unittest.TestCase):
    def make_packet(self, directory: Path) -> tuple[Path, Path]:
        helper = grouping_helpers.SecEdgarIapdPostCaptureGroupingV1Tests()
        release_path, release_qa_path, grouping_path = helper.make_release(directory)
        execute_grouping(release_path, release_qa_path)
        grouping_qa = verify_grouping(release_path, release_qa_path)
        grouping_qa_path = directory / "grouping_result_qa.json"
        grouping_qa_path.write_text(json.dumps(grouping_qa, indent=2) + "\n", encoding="utf-8")
        release = load_object(release_path)
        manifest_path = Path(release["inputs"]["exact_text_manifest"]["path"])
        packet = build(grouping_path, grouping_qa_path, manifest_path)
        packet_path = directory / "manual_group_packet.json"
        packet_path.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
        return packet_path, grouping_path

    def make_review(self, packet_path: Path) -> dict:
        packet = load_object(packet_path)
        rows = []
        for source in packet["records"]:
            routing = source["automated_screen"]["routing_decision"]
            opened_near = source["automated_screen"]["opened_overlap"]["probable_near_duplicate_hits"]
            if routing in AUTOMATED_EXCLUSIONS:
                decision = "CONFIRM_AUTOMATED_EXCLUSION"
                linked_opened = []
                evidence = []
            elif opened_near:
                decision = "ROUTE_OPENED_COHORT_CLONE_REVIEW"
                linked_opened = [opened_near[0]["record_exclusion_key"]]
                evidence = ["Frozen normalized-text near-duplicate metrics require opened-clone review."]
            else:
                decision = "KEEP_PROVISIONALLY_DISTINCT"
                linked_opened = []
                evidence = []
            rows.append({
                "record_id": source["record_id"],
                "group_decision": decision,
                "linked_record_ids": [],
                "canonical_record_id": None,
                "linked_opened_record_keys": linked_opened,
                "positive_linkage_evidence": evidence,
                "identity_or_content_flags_for_primary_review": [],
                "rationale": "The frozen local text, technical-group evidence, and exclusion routing were reviewed without model output or network access.",
                "ground_truth_status": "UNCERTAIN",
                "label_created": False,
                "training_eligible": "NO",
            })
        return {
            "review_id": "ISI_SEC_EDGAR_IAPD_MANUAL_GROUP_REVIEW_V1",
            "status": "MANUAL_GROUP_REVIEW_COMPLETE_STRUCTURAL_QA_REQUIRED",
            "input_packet": {"path": str(packet_path), "sha256": sha256_file(packet_path)},
            "reviewer": {"mode": "AI_ASSISTED_MANUAL_REVIEW_AUTHORIZED_BY_OWNER", "network_access_used": False, "model_predictions_visible": False, "source_membership_treated_as_label": False},
            "records": rows,
            "decision": {"binary_labeling_completed": False, "training_allowed": False},
        }

    def test_packet_and_review_keep_labels_closed_and_holdout_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            packet_path, _ = self.make_packet(directory)
            packet = load_object(packet_path)
            self.assertEqual(packet["record_count"], 2)
            review = self.make_review(packet_path)
            review_path = directory / "manual_group_review.json"
            review_path.write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
            qa = verify(packet_path, review_path)
            self.assertEqual(qa["status"], "PASS_GROUP_REVIEW_PRIMARY_PACKET_MAY_BE_PREPARED")
            self.assertEqual(qa["checks"]["unresolved_relationships"], 0)
            self.assertEqual(qa["checks"]["labels_created"], 0)
            holdout_id = next(row["record_id"] for row in packet["records"] if row["cohort"] == "EXTERNAL_HOLDOUT")
            holdout_review = next(row for row in review["records"] if row["record_id"] == holdout_id)
            self.assertEqual(holdout_review["group_decision"], "CONFIRM_AUTOMATED_EXCLUSION")

    def test_review_rejects_source_membership_as_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            packet_path, _ = self.make_packet(directory)
            review = self.make_review(packet_path)
            review["reviewer"]["source_membership_treated_as_label"] = True
            review_path = directory / "bad_review.json"
            review_path.write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
            qa = verify(packet_path, review_path)
            self.assertEqual(qa["status"], "FAIL")
            self.assertTrue(any("firewall" in error for error in qa["errors"]))


if __name__ == "__main__":
    unittest.main()
