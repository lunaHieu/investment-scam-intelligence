import json,unittest
from pathlib import Path
from scripts.verify_target_text_corpus_v1_ready_channel_capture_continuation_release_v2 import sha
ROOT=Path(__file__).resolve().parents[1]
RELEASE=ROOT/'configs'/'target_text_corpus_v1_ready_channel_capture_continuation_release_v2.json'
REPORT=Path(r'D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\ready_channel_wayback_capture_continuation_result_v2\capture_report_continuation_v2.json')
QA=REPORT.parent/'independent_result_qa_v2.json'
PLAN49=Path(r'D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\ready_channel_wayback_capture_continuation_plan_v1\capture_continuation_plan_v1.json')
PLAN49_QA=PLAN49.parent/'independent_plan_qa_v1.json'
PLAN48=Path(r'D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\ready_channel_wayback_capture_continuation_plan_v2\capture_continuation_plan_v2.json')
PLAN48_QA=PLAN48.parent/'independent_plan_qa_v2.json'
class CurrentArtifactLifecycleV6Tests(unittest.TestCase):
 def test_consumed_exact_48_continuation_and_partial_result_verify(self):
  report=json.loads(REPORT.read_text());qa=json.loads(QA.read_text())
  self.assertEqual(sha(RELEASE),'e43bb1838bd7f7187451a0f667b58f7a5c816aeae9760e2ac9228337345e2bb5')
  self.assertEqual(sha(REPORT),'639a9d80c957fcf497d9b010086ff077f9432306136db6b94bc5a2e8d3a81e31')
  self.assertEqual(sha(QA),'378bcdb08f10a6fc0357a2e4c28b9939d83f89c1a3c91822b135f2d9b4a65bbe')
  self.assertEqual((report['captured_count'],report['failed_provider_or_transport_count'],report['not_attempted_count']),(5,1,42))
  self.assertEqual(qa['status'],'PASS_PARTIAL_PROVIDER_FAILURE_PRESERVED');self.assertTrue(qa['checks']['byte_hashes_verified'])
 def test_consumed_exact_49_plan_membership(self):
  p=json.loads(PLAN49.read_text());self.assertEqual(sha(PLAN49),'c7ca76672726659564c5dba9595bdd46c5e295c9897932814ff86456dc215457');self.assertEqual(len(p['results']),49)
 def test_consumed_exact_49_plan_qa(self):
  q=json.loads(PLAN49_QA.read_text());self.assertEqual(sha(PLAN49_QA),'87e58682839002f333852a9b1ab9d455cdc839f23330ef76a9b1828f1b23c4d1');self.assertEqual(q['status'],'PASS_EXACT_49_NEVER_ATTEMPTED_CONTINUATION_PLAN')
 def test_consumed_exact_48_plan_membership(self):
  p=json.loads(PLAN48.read_text());self.assertEqual(sha(PLAN48),'91417bf9bacd4f1d36798203215ec20662d72c1442cf237ce4651a6a9a208441');self.assertEqual(len(p['results']),48)
 def test_consumed_exact_48_plan_qa(self):
  q=json.loads(PLAN48_QA.read_text());self.assertEqual(sha(PLAN48_QA),'9ea892fe234113d5fb258c0b4d15d3563f8a71e7ecb135fd9789efd5214896eb');self.assertEqual(q['status'],'PASS_EXACT_48_NEVER_ATTEMPTED_CONTINUATION_PLAN')
if __name__=='__main__':unittest.main()
