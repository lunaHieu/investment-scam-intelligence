import unittest
from pathlib import Path
from scripts.verify_target_text_corpus_v1_ready_channel_capture_continuation_release_v1 import PASS_STATUS,verify
ROOT=Path(__file__).resolve().parents[1];RELEASE=ROOT/'configs'/'target_text_corpus_v1_ready_channel_capture_continuation_release_v1.json'
class ContinuationReleaseV1Tests(unittest.TestCase):
 def test_real_release_is_exact_49_and_verified(self):
  v=verify(RELEASE);self.assertEqual(v['status'],PASS_STATUS,v['errors']);self.assertEqual(v['checks']['record_count'],49);self.assertTrue(v['checks']['planned_output_absent'])
if __name__=='__main__':unittest.main()
