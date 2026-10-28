import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_ready_channel_capture_continuation_plan_v2 import verify


PLAN = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\ready_channel_wayback_capture_continuation_plan_v2\capture_continuation_plan_v2.json")


class ContinuationPlanV2Tests(unittest.TestCase):
    def test_real_plan_is_exact_48_and_recomputes(self):
        result = verify(PLAN)
        self.assertEqual(result["status"], "PASS_EXACT_48_NEVER_ATTEMPTED_CONTINUATION_PLAN", result["errors"])
        self.assertEqual(result["checks"]["planned_rows"], 48)

    def test_failed_rows_are_disjoint(self):
        result = verify(PLAN)
        self.assertTrue(result["checks"]["quarantined_rows_excluded"])


if __name__ == "__main__":
    unittest.main()
