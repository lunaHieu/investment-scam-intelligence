import json,unittest
from pathlib import Path
from scripts.verify_target_text_corpus_v1_ready_channel_capture_continuation_release_v1 import sha
ROOT=Path(__file__).resolve().parents[1]
class ContinuationRegistriesV1Tests(unittest.TestCase):
 def test_registries_pin_inputs(self):
  for name in ('target_text_corpus_v1_ready_channel_capture_continuation_plan_v1.json','target_text_corpus_v1_ready_channel_capture_continuation_release_v1.json','target_text_corpus_v1_ready_channel_row009_diagnostic_protocol_v1.json'):
   v=json.loads((ROOT/'registry'/'analyses'/name).read_text());
   for item in v['inputs']:
    p=Path(item['path']);p=p if p.is_absolute() else ROOT/p;self.assertEqual(sha(p),item['sha256'])
 def test_network_boundaries(self):
  p=json.loads((ROOT/'registry'/'analyses'/'target_text_corpus_v1_ready_channel_capture_continuation_release_v1.json').read_text());self.assertEqual(p['findings']['record_count'],49);self.assertFalse(p['findings']['failed_row_009_included'])
if __name__=='__main__':unittest.main()
