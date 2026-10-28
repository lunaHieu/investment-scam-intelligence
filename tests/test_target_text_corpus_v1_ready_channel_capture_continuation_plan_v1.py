import tempfile
import unittest
from pathlib import Path

from scripts.build_target_text_corpus_v1_ready_channel_capture_continuation_plan_v1 import build
from scripts.verify_target_text_corpus_v1_ready_channel_capture_continuation_plan_v1 import verify


SOURCE = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\ready_channel_wayback_capture_plan_v1\capture_plan_v1.json")
REPORT = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\ready_channel_wayback_capture_result_v1\capture_report_v1.json")
QA = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\ready_channel_wayback_capture_result_v1\independent_result_qa_v1.json")


class ReadyChannelCaptureContinuationPlanV1Tests(unittest.TestCase):
    def test_exact_49_excludes_successes_and_failure(self) -> None:
        plan = build(SOURCE, REPORT, QA)
        ids = [row["availability_plan_id"] for row in plan["results"]]
        self.assertEqual(len(ids), 49)
        self.assertNotIn("TTCV1_B3_AVAIL_009", ids)
        self.assertTrue(set(["TTCV1_B3_AVAIL_002", "TTCV1_B3_AVAIL_003", "TTCV1_B3_AVAIL_005"]).isdisjoint(ids))

    def test_independent_full_recomputation_passes(self) -> None:
        plan = build(SOURCE, REPORT, QA)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            import json
            path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            result = verify(path)
        self.assertEqual(result["status"], "PASS_EXACT_49_NEVER_ATTEMPTED_CONTINUATION_PLAN", result["errors"])


if __name__ == "__main__":
    unittest.main()
