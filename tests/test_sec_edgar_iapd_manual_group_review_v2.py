import json
import tempfile
import unittest
from pathlib import Path

from scripts.materialize_sec_edgar_iapd_manual_group_review_v2 import build_review
from scripts.verify_sec_edgar_iapd_manual_group_review_v2 import verify


PACKET = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\sec_edgar_iapd_post_capture_grouping_result_v2\manual_group_review_packet_v2.json")


class SecEdgarIapdManualGroupReviewV2Tests(unittest.TestCase):
    def test_real_frozen_packet_review_is_complete_conservative_and_label_free(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            review = build_review(PACKET)
            self.assertEqual(len(review["records"]), 56)
            self.assertTrue(all(row["group_decision"] == "KEEP_PROVISIONALLY_DISTINCT" for row in review["records"]))
            self.assertTrue(all(row["ground_truth_status"] == "UNCERTAIN" for row in review["records"]))
            review_path = Path(tmp) / "review.json"
            review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            qa = verify(PACKET, review_path)
            self.assertEqual(qa["status"], "PASS_CAPTURED_SUBSET_GROUP_REVIEW_PRIMARY_PACKET_MAY_BE_PREPARED")
            self.assertEqual(qa["checks"]["primary_review_candidate_count"], 56)
            self.assertEqual(qa["checks"]["labels_created"], 0)


if __name__ == "__main__":
    unittest.main()
