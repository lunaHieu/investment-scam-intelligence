import unittest
from pathlib import Path
from scripts.verify_target_text_corpus_v1_ready_channel_capture_continuation_plan_v3 import verify
PLAN=Path(r'D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\ready_channel_wayback_capture_continuation_plan_v3\capture_continuation_plan_v3.json')
class PlanV3Tests(unittest.TestCase):
 def test_exact_42_recomputes(self):
  v=verify(PLAN);self.assertEqual(v['status'],'PASS_EXACT_42_NEVER_ATTEMPTED_CONTINUATION_PLAN',v['errors']);self.assertEqual(v['checks']['planned'],42)
if __name__=='__main__':unittest.main()
