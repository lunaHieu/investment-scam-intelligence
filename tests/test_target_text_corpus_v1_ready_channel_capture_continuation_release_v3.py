import unittest
from pathlib import Path
from scripts.verify_target_text_corpus_v1_ready_channel_capture_continuation_release_v3 import PASS_STATUS,verify
R=Path(__file__).resolve().parents[1]/'configs'/'target_text_corpus_v1_ready_channel_capture_continuation_release_v3.json'
class ReleaseV3Tests(unittest.TestCase):
 def test_release(self):
  v=verify(R);self.assertEqual(v['status'],PASS_STATUS,v['errors']);self.assertEqual(v['checks']['rows'],42);self.assertTrue(v['checks']['output_absent'])
if __name__=='__main__':unittest.main()
