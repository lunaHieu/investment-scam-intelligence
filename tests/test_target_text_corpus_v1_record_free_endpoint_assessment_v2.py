import unittest
from scripts.record_free_endpoint_assessment_v2 import assemble_result,verify_release

class RecordFreeEndpointAssessmentV2Tests(unittest.TestCase):
 def test_release(self):
  self.assertEqual(verify_release()["status"],"PASS_RECORD_FREE_ENDPOINT_V2_RELEASE_VERIFIED")
 def test_result_assembly_uses_python_booleans(self):
  value=assemble_result([],"0"*64);self.assertIs(value["decision"]["content_get_release_allowed"],False);self.assertEqual(value["results"],[])
if __name__=="__main__":unittest.main()
