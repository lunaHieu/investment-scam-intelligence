import unittest
from scripts.verify_target_text_corpus_v1_parser_bound_content_release_v1 import verify
class ParserBoundContentReleaseV1Tests(unittest.TestCase):
 def test_local_candidate_is_verified_but_execution_closed(self):
  self.assertEqual(verify()["status"],"PASS_LOCAL_PARSER_BOUND_RELEASE_VERIFIED_EXECUTION_CLOSED")
if __name__=="__main__":unittest.main()
