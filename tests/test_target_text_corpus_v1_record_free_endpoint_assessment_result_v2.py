import unittest
from scripts.verify_target_text_corpus_v1_record_free_endpoint_assessment_result_v2 import verify
class ResultV2Tests(unittest.TestCase):
 def test_result(self):self.assertEqual(verify(),{"status":"PASS_HEAD_ONLY_RESULT_V2_VERIFIED","endpoints":8,"http_200":7,"http_307":1,"response_bodies_read":0,"content_get_authorized":0})
if __name__=="__main__":unittest.main()
