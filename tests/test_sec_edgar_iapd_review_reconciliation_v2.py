import json
import unittest
from pathlib import Path

from scripts.verify_sec_edgar_iapd_blind_second_review_v2 import verify as verify_second
from scripts.verify_sec_edgar_iapd_primary_review_v2 import verify as verify_primary
from scripts.verify_sec_edgar_iapd_reconciliation_v2 import verify as verify_reconciliation


BASE = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\sec_edgar_iapd_post_capture_grouping_result_v2")


class SecEdgarIapdReviewReconciliationV2Tests(unittest.TestCase):
    def test_real_review_stack_reproduces_and_keeps_owner_gate_closed(self) -> None:
        primary = verify_primary(BASE / "primary_review_packet_v2.json", BASE / "primary_review_v2.json")
        self.assertEqual(primary["status"], "PASS_CAPTURED_SUBSET_PRIMARY_REVIEW_BLIND_SECOND_REVIEW_MAY_BE_PREPARED")
        self.assertEqual(primary["checks"]["recommendation_counts"], {"LEGITIMATE": 47, "UNCERTAIN": 9})
        second = verify_second(BASE / "blind_second_review_packet_v2.json", BASE / "blind_second_review_v2.json")
        self.assertEqual(second["status"], "PASS_CAPTURED_SUBSET_BLIND_SECOND_REVIEW_RECONCILIATION_MAY_BE_PREPARED")
        self.assertEqual(second["checks"]["recommendation_counts"], {"LEGITIMATE": 44, "UNCERTAIN": 12})
        reconciliation = verify_reconciliation(BASE / "reconciliation_v2.json")
        self.assertEqual(reconciliation["status"], "PASS_CAPTURED_SUBSET_RECONCILIATION_REPRODUCED_OWNER_ACCEPTANCE_REQUIRED")
        self.assertEqual(reconciliation["checks"]["record_count"], 56)
        self.assertEqual(reconciliation["checks"]["review_disagreements"], 7)
        self.assertEqual(reconciliation["checks"]["owner_acceptance_pending"], 56)
        self.assertFalse(reconciliation["decision"]["materialization_allowed_now"])
        result = json.loads((BASE / "reconciliation_v2.json").read_text(encoding="utf-8"))
        self.assertEqual(result["summary"]["reconciled_recommendation_counts"], {"LEGITIMATE": 42, "UNCERTAIN": 14})
        self.assertEqual(result["summary"]["labels_created"], 0)


if __name__ == "__main__":
    unittest.main()
