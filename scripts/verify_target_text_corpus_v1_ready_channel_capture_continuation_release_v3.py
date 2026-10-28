"""Verify the exact-42 V3 capture release."""
from __future__ import annotations
import argparse,json
from datetime import datetime
from pathlib import Path
from scripts.verify_target_text_corpus_v1_ready_channel_capture_continuation_release_v2 import ROOT,load,sha
PASS_STATUS='PASS_FROZEN_EXACT_42_CAPTURE_CONTINUATION_RELEASE'
def verify(path:Path,require_output_absent=True):
 r=load(path);e=[]
 if r.get('release_id')!='ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_CAPTURE_CONTINUATION_RELEASE_V3':e.append('identity')
 for x in r.get('tooling',[]):
  p=ROOT/x['path']
  if not p.is_file() or sha(p)!=x['sha256']:e.append('tool '+x['path'])
 pr,qr=r['inputs']['plan'],r['inputs']['qa'];pp,qp=Path(pr['path']),Path(qr['path'])
 if sha(pp)!=pr['sha256'] or sha(qp)!=qr['sha256']:e.append('input hash')
 p,q=load(pp),load(qp);rows=p.get('results',[])
 if len(rows)!=42 or q.get('status')!='PASS_EXACT_42_NEVER_ATTEMPTED_CONTINUATION_PLAN':e.append('plan')
 if [x['availability_plan_id'] for x in rows]!=r['identity_contract']['ordered_ids']:e.append('order')
 if any(Path(x['capture_path']).exists() for x in rows):e.append('target exists')
 c=r['execution_contract']
 for k,v in {'minimum_delay_seconds':30.0,'maximum_attempts_per_snapshot':1,'row_local_http_statuses':[404,410],'stop_on_http_429':True,'stop_on_http_5xx':True,'stop_on_transport_error':True,'preserve_all_response_bytes':True,'automatic_resume_allowed':False}.items():
  if c.get(k)!=v:e.append('contract '+k)
 if datetime.fromisoformat(c['not_before'])<datetime.fromisoformat(r['created_at']):e.append('time')
 o=Path(r['output']['report']);states=[o,o.with_suffix(o.suffix+'.partial'),o.with_suffix(o.suffix+'.finalizing')]
 if require_output_absent and any(x.exists() for x in states):e.append('output exists')
 return {'verification_id':'ISI_TTCV1_CAPTURE_CONTINUATION_RELEASE_QA_V3','status':PASS_STATUS if not e else 'FAIL','release':{'path':str(path.resolve()),'sha256':sha(path)},'checks':{'rows':len(rows),'output_absent':not any(x.exists() for x in states)},'errors':e}
def main():
 p=argparse.ArgumentParser();p.add_argument('--release',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise FileExistsError(a.output)
 v=verify(a.release);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(v,indent=2)+'\n');print(json.dumps(v,indent=2));return 0 if not v['errors'] else 1
if __name__=='__main__':raise SystemExit(main())
