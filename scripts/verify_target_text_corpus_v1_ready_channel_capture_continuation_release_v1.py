"""Verify the exact-49 ready-channel capture continuation release."""
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PASS_STATUS="PASS_FROZEN_EXACT_49_CAPTURE_CONTINUATION_RELEASE"
def sha(path:Path)->str:
 d=hashlib.sha256();
 with path.open('rb') as h:
  for c in iter(lambda:h.read(1048576),b''): d.update(c)
 return d.hexdigest()
def load(path:Path): return json.loads(path.read_text(encoding='utf-8'))
def verify(path:Path,require_output_absent:bool=True):
 r=load(path); errors=[]
 if r.get('release_id')!='ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_CAPTURE_CONTINUATION_RELEASE_V1' or r.get('status')!='FROZEN_EXACT_49_NEVER_ATTEMPTED_CAPTURE_CONTINUATION': errors.append('release identity changed')
 for item in r.get('tooling',[]):
  p=ROOT/item['path']
  if not p.is_file() or sha(p)!=item['sha256']: errors.append(f"tooling hash mismatch: {item['path']}")
 pi,qi=r['inputs']['continuation_plan'],r['inputs']['independent_plan_qa']; pp,qp=Path(pi['path']),Path(qi['path'])
 if sha(pp)!=pi['sha256'] or sha(qp)!=qi['sha256']: errors.append('plan evidence hash mismatch')
 plan,qa=load(pp),load(qp); rows=plan.get('results',[])
 if len(rows)!=49 or plan.get('status')!='FROZEN_EXACT_49_NEVER_ATTEMPTED_ONLY_CAPTURE_PLAN': errors.append('plan is not exact 49')
 if qa.get('status')!='PASS_EXACT_49_NEVER_ATTEMPTED_CONTINUATION_PLAN' or qa.get('plan',{}).get('sha256')!=pi['sha256']: errors.append('plan QA mismatch')
 if [x['availability_plan_id'] for x in rows]!=r.get('identity_contract',{}).get('ordered_availability_plan_ids'): errors.append('identity order changed')
 if any(Path(x['capture_path']).exists() for x in rows): errors.append('continuation target exists')
 c=r.get('execution_contract',{}); expected={'minimum_delay_seconds':30.0,'maximum_attempts_per_snapshot':1,'stop_on_any_error':True,'automatic_resume_allowed':False,'output_overwrite_allowed':False,'separate_invocation_required':True}
 for k,v in expected.items():
  if c.get(k)!=v: errors.append(f'contract changed: {k}')
 try:
  if datetime.fromisoformat(c['not_before'])<datetime.fromisoformat(r['created_at']): errors.append('not-before predates creation')
 except ValueError: errors.append('invalid timestamp')
 out=Path(r['planned_output']['path']); states=[out,out.with_suffix(out.suffix+'.partial'),out.with_suffix(out.suffix+'.finalizing')]
 if require_output_absent and any(x.exists() for x in states): errors.append('output exists')
 return {'verification_id':'ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_CAPTURE_CONTINUATION_RELEASE_QA_V1','status':PASS_STATUS if not errors else 'FAIL','release':{'path':str(path.resolve()),'sha256':sha(path)},'checks':{'record_count':len(rows),'planned_output_absent':not any(x.exists() for x in states),'not_before':c.get('not_before')},'decision':{'execution_allowed_in_separate_invocation':not errors,'candidate_live_domain_access_allowed':False,'labeling_allowed':False,'training_allowed':False},'errors':errors,'safety_contract':{'network_operations':0,'captures':0,'labels':0,'model':0}}
def main():
 p=argparse.ArgumentParser();p.add_argument('--release',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists(): raise FileExistsError(a.output)
 v=verify(a.release);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8');print(json.dumps(v,indent=2));return 0 if not v['errors'] else 1
if __name__=='__main__': raise SystemExit(main())
