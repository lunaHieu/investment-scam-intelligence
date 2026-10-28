"""Verify V3 capture and diagnostic bytes."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from scripts.verify_target_text_corpus_v1_ready_channel_capture_continuation_release_v3 import load,sha
def verify(rp,qp,reportp):
 r,report=load(rp),load(reportp);plan=load(Path(r['inputs']['plan']['path']));e=[]
 if [x['capture_plan_id'] for x in plan['results']]!=[x['capture_plan_id'] for x in report['results']]:e.append('order')
 for x in report['results']:
  p=Path(x['capture_path'])
  if x['outcome']=='CAPTURED':
   if not p.is_file() or p.stat().st_size!=x['bytes'] or sha(p)!=x['sha256']:e.append(x['capture_plan_id'])
  elif x['outcome'].startswith('QUARANTINED'):
   d=Path(x['raw_response_path'])
   if p.exists() or not d.is_file() or d.stat().st_size!=x['bytes'] or sha(d)!=x['sha256']:e.append(x['capture_plan_id'])
 complete=report['not_attempted_count']==0 and report['failed_count']==0
 return {'verification_id':'ISI_TTCV1_CAPTURE_CONTINUATION_RESULT_QA_V3','status':'PASS_COMPLETE_42_POPULATION' if complete and not e else 'PASS_PARTIAL_PRESERVED' if not e else 'FAIL','inputs':{'release_sha256':sha(rp),'release_qa_sha256':sha(qp),'report_sha256':sha(reportp)},'checks':{'planned':42,'captured':report['captured_count'],'quarantined':report['quarantined_count'],'complete_population':complete,'byte_hashes_verified':not e},'decision':{'reconciliation_may_be_prepared':complete and not e,'automatic_retry_allowed':False,'labeling_allowed':False,'training_allowed':False},'errors':e}
def main():
 p=argparse.ArgumentParser();p.add_argument('--release',type=Path,required=True);p.add_argument('--release-qa',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise FileExistsError(a.output)
 v=verify(a.release,a.release_qa,a.report);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(v,indent=2)+'\n');print(json.dumps(v,indent=2));return 0 if not v['errors'] else 1
if __name__=='__main__':raise SystemExit(main())
