import json,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'configs/target_text_corpus_v1_sanitized_text_only_intake_protocol_v1.json'
class SanitizedTextProtocolV1Tests(unittest.TestCase):
 def test_active_formats_and_network_are_forbidden(self):
  v=json.loads(P.read_text());self.assertIn('HTML',v['scope']['forbidden_types']);self.assertFalse(v['scope']['candidate_live_domain_access_allowed']);self.assertFalse(v['scope']['link_following_allowed'])
 def test_detection_abandons_batch_and_training_closed(self):
  v=json.loads(P.read_text());self.assertEqual(v['failure_policy']['malware_or_pua_detection'],'ABANDON_BATCH_NO_RESTORE_NO_WHITELIST');self.assertFalse(v['decision']['acquisition_authorized']);self.assertFalse(v['decision']['training_allowed'])
if __name__=='__main__':unittest.main()
