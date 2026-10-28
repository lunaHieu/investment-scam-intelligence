"""Execute the exact-49 ready-channel capture continuation once."""
from __future__ import annotations
import argparse, hashlib, json
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from scripts.execute_target_text_corpus_v1_ready_channel_capture_v1 import fetch
from scripts.verify_target_text_corpus_v1_ready_channel_capture_continuation_release_v1 import PASS_STATUS,load,sha,verify

def validate(rp:Path,qp:Path):
 r,q=load(rp),load(qp);v=verify(rp)
 if q.get('status')!=PASS_STATUS or q.get('release',{}).get('sha256')!=sha(rp) or v['status']!=PASS_STATUS: raise ValueError('continuation release QA failed')
 return r,load(Path(r['inputs']['continuation_plan']['path']))
def execute(rp:Path,qp:Path):
 r,plan=validate(rp,qp); now=datetime.now(timezone.utc).astimezone()
 if now<datetime.fromisoformat(r['execution_contract']['not_before']): raise PermissionError('not-before closed')
 out=Path(r['planned_output']['path']);partial=out.with_suffix(out.suffix+'.partial');final=out.with_suffix(out.suffix+'.finalizing')
 if any(x.exists() for x in (out,partial,final)): raise FileExistsError('output exists')
 out.parent.mkdir(parents=True,exist_ok=True);partial.write_text(json.dumps({'status':'RESERVED_BEFORE_NETWORK_NON_RESUMABLE','release_sha256':sha(rp),'automatic_resume_allowed':False},indent=2)+'\n',encoding='utf-8')
 counter=[0];results=[];stopped=False
 for s in plan['results']:
  base={k:s[k] for k in ('capture_plan_id','availability_plan_id','candidate_id','cohort','channel_id','candidate_host','snapshot_timestamp','snapshot_original_url','snapshot_digest','requested_archive_url','capture_path')}
  if stopped: results.append({**base,'outcome':'NOT_ATTEMPTED_AFTER_ERROR_STOP','attempt_count':0,'bytes':None,'sha256':None,'error':'NOT_ATTEMPTED_AFTER_ERROR_STOP'});continue
  try:
   payload,url,redirects,ctype,diag=fetch(s['requested_archive_url'],r['execution_contract'],counter);target=Path(s['capture_path']);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(payload)
   results.append({**base,'outcome':'CAPTURED','attempt_count':1,'final_archive_url':url,'redirect_count':redirects,'http_status':200,'content_type':ctype,'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest(),'diagnostics':diag,'error':None})
  except Exception as e:
   stopped=True;results.append({**base,'outcome':'FAILED','attempt_count':1,'bytes':None,'sha256':None,'error':f'{type(e).__name__}: {e}'})
 cap=sum(x['outcome']=='CAPTURED' for x in results);report={'report_id':r['planned_output']['report_id'],'created_at':now.isoformat(),'status':'COMPLETE' if cap==49 else 'INCOMPLETE_FAILURES_PRESERVED','release':{'sha256':sha(rp)},'release_qa':{'sha256':sha(qp)},'plan':r['inputs']['continuation_plan'],'planned_capture_count':49,'network_request_count':counter[0],'captured_count':cap,'captured_by_cohort':dict(Counter(x['cohort'] for x in results if x['outcome']=='CAPTURED')),'failed_count':sum(x['outcome']=='FAILED' for x in results),'not_attempted_count':sum(x['outcome'].startswith('NOT_ATTEMPTED') for x in results),'stopped_on_error':stopped,'results':results,'safety_contract':{'candidate_live_domain_access_operations':0,'labels_created':0,'model_operations':0,'training_allowed':False}}
 final.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');final.replace(out);partial.unlink();return report
def main():
 p=argparse.ArgumentParser();p.add_argument('--release',type=Path,required=True);p.add_argument('--release-qa',type=Path,required=True);p.add_argument('--verify-only',action='store_true');a=p.parse_args()
 if a.verify_only:
  r,plan=validate(a.release,a.release_qa);print(json.dumps({'valid':True,'planned_capture_count':len(plan['results']),'seconds_until_not_before':max(0,round((datetime.fromisoformat(r['execution_contract']['not_before'])-datetime.now(timezone.utc).astimezone()).total_seconds()))},indent=2));return 0
 report=execute(a.release,a.release_qa);print(json.dumps({k:report[k] for k in ('status','network_request_count','captured_count','failed_count','not_attempted_count')},indent=2));return 0 if report['status']=='COMPLETE' else 2
if __name__=='__main__': raise SystemExit(main())
