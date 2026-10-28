import json,unittest
from pathlib import Path
from scripts.verify_target_text_corpus_v1_ready_channel_capture_continuation_release_v2 import sha
ROOT=Path(__file__).resolve().parents[1];REPORT=Path(r'D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\ready_channel_wayback_capture_continuation_result_v3\capture_report_continuation_v3.json')
class CurrentArtifactLifecycleV7Tests(unittest.TestCase):
 def test_consumed_plan_and_report_are_pinned(self):
  r=json.loads(REPORT.read_text());self.assertEqual(sha(REPORT),'6c694fa6ef1df1e6d344d443dfa2d99744f7e9e3b59cd792cdc1d60e918bf78d');self.assertEqual((r['captured_count'],r['quarantined_count'],r['not_attempted_count']),(40,2,0))
 def test_endpoint_security_incident_is_fail_closed(self):
  i=json.loads((ROOT/'registry/analyses/target_text_corpus_v1_ready_channel_raw_artifact_security_incident_v1.json').read_text());self.assertFalse(i['decision']['raw_html_processing_allowed']);self.assertFalse(i['decision']['restore_allowed'])
if __name__=='__main__':unittest.main()
