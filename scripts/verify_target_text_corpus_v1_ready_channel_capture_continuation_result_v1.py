"""Verify exact-49 continuation capture bytes."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from scripts.verify_target_text_corpus_v1_ready_channel_capture_continuation_release_v1 import load,sha
def verify(rp:Path,qp:Path,reportp:Path):
 r,q,report=load(rp),load(qp),load(reportp);plan=load(Path(r['inputs']['continuation_plan']['path']));errors=[];expected={x['capture_plan_id']:x for x in plan['results']};actual={x['capture_plan_id']:x for x in report['results']}
 if list(expected)!=list(actual): errors.append('membership/order changed')
 captured=0
 for k,x in actual.items():
  target=Path(x['capture_path'])
  if x['outcome']=='CAPTURED':
   captured+=1
   if not target.is_file() or target.stat().st_size!=x['bytes'] or sha(target)!=x['sha256']: errors.append(f'byte/hash mismatch: {k}')
  elif target.exists(): errors.append(f'non-captured target exists: {k}')
 complete=captured==49 and report['status']=='COMPLETE';return {'verification_id':'ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_CAPTURE_CONTINUATION_RESULT_QA_V1','status':'PASS_COMPLETE_49_CONTINUATION_CAPTURES' if complete and not errors else 'PASS_PARTIAL_CONTINUATION_PRESERVED' if not errors else 'FAIL','inputs':{'release_sha256':sha(rp),'release_qa_sha256':sha(qp),'report_sha256':sha(reportp)},'checks':{'planned':49,'captured':captured,'complete':complete,'byte_hashes_verified':not errors},'decision':{'combined_capture_reconciliation_may_be_prepared':complete and not errors,'automatic_retry_allowed':False,'labeling_allowed':False,'training_allowed':False},'errors':errors}
def main():
 p=argparse.ArgumentParser();p.add_argument('--release',type=Path,required=True);p.add_argument('--release-qa',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();v=verify(a.release,a.release_qa,a.report);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8');print(json.dumps(v,indent=2));return 0 if not v['errors'] else 1
if __name__=='__main__': raise SystemExit(main())
