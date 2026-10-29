import json,unittest
from pathlib import Path
from scripts.verify_target_text_corpus_v1_ready_channel_capture_continuation_release_v2 import sha
ROOT=Path(__file__).resolve().parents[1];P=ROOT/'configs/target_text_corpus_v1_sanitized_text_only_inventory_v1.json'
class SanitizedTextInventoryV1Tests(unittest.TestCase):
 def test_hashes_and_totals(self):
  v=json.loads(P.read_text());
  for x in v['inputs']:self.assertEqual(sha(ROOT/x['path']),x['sha256'])
  self.assertEqual(v['totals']['safe_text_raw_rows_present'],16202);self.assertEqual(v['totals']['authorized_historical_train_rows'],3916);self.assertEqual(v['totals']['fresh_v1_core_admitted_groups'],0)
 def test_abandoned_and_metadata_sources_have_zero_credit(self):
  v=json.loads(P.read_text());self.assertTrue(all(x['v1_core_credit']==0 for x in v['inventory']));self.assertFalse(v['decision']['training_allowed'])
if __name__=='__main__':unittest.main()
