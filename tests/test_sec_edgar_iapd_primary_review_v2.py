import json
import tempfile
import unittest
from pathlib import Path

from scripts.materialize_sec_edgar_iapd_primary_review_v2 import build_review
from scripts.verify_sec_edgar_iapd_primary_review_v2 import verify


PACKET = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\sec_edgar_iapd_post_capture_grouping_result_v2\primary_review_packet_v2.json")


class SecEdgarIapdPrimaryReviewV2Tests(unittest.TestCase):
    def test_real_packet_review_is_conservative_and_label_free(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            review = build_review(PACKET)
            counts = {value: sum(row["primary_recommendation"] == value for row in review["records"]) for value in ("LEGITIMATE", "UNCERTAIN")}
            self.assertEqual(counts, {"LEGITIMATE": 47, "UNCERTAIN": 9})
            review_path = Path(tmp) / "review.json"
            review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            qa = verify(PACKET, review_path)
            self.assertEqual(qa["status"], "PASS_CAPTURED_SUBSET_PRIMARY_REVIEW_BLIND_SECOND_REVIEW_MAY_BE_PREPARED")
            self.assertEqual(qa["checks"]["labels_created"], 0)


if __name__ == "__main__":
    unittest.main()
