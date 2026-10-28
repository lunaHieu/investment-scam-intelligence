"""Execute exact-42 V3, quarantining preserved HTTP 404/410 responses."""
from __future__ import annotations
import argparse,hashlib,json
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from scripts.execute_target_text_corpus_v1_ready_channel_capture_continuation_v2 import ArchiveProviderError,USER_AGENT,fetch_response,_write_journal
from scripts.verify_target_text_corpus_v1_ready_channel_capture_continuation_release_v3 import PASS_STATUS,load,sha,verify
def validate(rp,qp):
 r,q=load(rp),load(qp);v=verify(rp)
 if q.get('status')!=PASS_STATUS or q.get('release',{}).get('sha256')!=sha(rp) or v['status']!=PASS_STATUS:raise ValueError('release QA')
 return r,load(Path(r['inputs']['plan']['path']))
def execute(rp,qp):
 r,p=validate(rp,qp);now=datetime.now(timezone.utc).astimezone()
 if now<datetime.fromisoformat(r['execution_contract']['not_before']):raise PermissionError('gate')
 out=Path(r['output']['report']);part=out.with_suffix(out.suffix+'.partial');fin=out.with_suffix(out.suffix+'.finalizing')
 if any(x.exists() for x in (out,part,fin)):raise FileExistsError('output')
 out.parent.mkdir(parents=True,exist_ok=True);count=[0];res=[];stop=False;_write_journal(part,sha(rp),0,res);c=r['execution_contract'];dr=Path(r['output']['diagnostics_root'])
 for s in p['results']:
  base={k:s[k] for k in ('capture_plan_id','availability_plan_id','candidate_id','cohort','channel_id','candidate_host','snapshot_timestamp','snapshot_original_url','snapshot_digest','requested_archive_url','capture_path')}
  if stop:res.append({**base,'outcome':'NOT_ATTEMPTED_AFTER_PROVIDER_ERROR_STOP','attempt_count':0,'bytes':None,'sha256':None});continue
  dp=dr/s['cohort']/(s['availability_plan_id']+'.bin')
  try:
   z=fetch_response(s['requested_archive_url'],c,count);b=z['payload'];h=hashlib.sha256(b).hexdigest();valid=z['status']==200 and z['content_type'].lower().startswith('text/html') and c['minimum_response_bytes']<=len(b)<=c['maximum_response_bytes']
   if valid:
    t=Path(s['capture_path']);t.parent.mkdir(parents=True,exist_ok=True);t.write_bytes(b);res.append({**base,'outcome':'CAPTURED','attempt_count':1,'http_status':200,'bytes':len(b),'sha256':h,'diagnostics':z['diagnostics']})
   else:
    dp.parent.mkdir(parents=True,exist_ok=True);dp.write_bytes(b);res.append({**base,'outcome':'QUARANTINED_ROW_LOCAL_RESPONSE','attempt_count':1,'http_status':z['status'],'bytes':len(b),'sha256':h,'raw_response_path':str(dp),'diagnostics':z['diagnostics']})
  except ArchiveProviderError as x:
   if x.status in c['row_local_http_statuses'] and x.payload:
    dp.parent.mkdir(parents=True,exist_ok=True);dp.write_bytes(x.payload);res.append({**base,'outcome':'QUARANTINED_ROW_LOCAL_HTTP','attempt_count':1,'http_status':x.status,'bytes':len(x.payload),'sha256':hashlib.sha256(x.payload).hexdigest(),'raw_response_path':str(dp),'diagnostics':x.diagnostics})
   else:
    stop=True;res.append({**base,'outcome':'FAILED_PROVIDER_OR_TRANSPORT','attempt_count':1,'http_status':x.status,'bytes':len(x.payload) if x.payload else None,'sha256':hashlib.sha256(x.payload).hexdigest() if x.payload else None,'diagnostics':x.diagnostics,'error':str(x)})
  _write_journal(part,sha(rp),count[0],res)
 cap=sum(x['outcome']=='CAPTURED' for x in res);qua=sum(x['outcome'].startswith('QUARANTINED') for x in res);fail=sum(x['outcome']=='FAILED_PROVIDER_OR_TRANSPORT' for x in res);na=sum(x['outcome'].startswith('NOT_ATTEMPTED') for x in res);status='COMPLETE' if cap==42 else 'COMPLETE_WITH_QUARANTINES' if cap+qua==42 and not fail else 'INCOMPLETE_PROVIDER_FAILURE_PRESERVED'
 report={'report_id':r['output']['report_id'],'created_at':now.isoformat(),'status':status,'release':{'sha256':sha(rp)},'release_qa':{'sha256':sha(qp)},'plan':r['inputs']['plan'],'planned_capture_count':42,'network_request_count':count[0],'captured_count':cap,'captured_by_cohort':dict(Counter(x['cohort'] for x in res if x['outcome']=='CAPTURED')),'quarantined_count':qua,'failed_count':fail,'not_attempted_count':na,'results':res,'safety_contract':{'candidate_live_domain_access_operations':0,'labels_created':0,'model_operations':0}}
 fin.write_text(json.dumps(report,indent=2)+'\n');fin.replace(out);part.unlink();return report
def main():
 p=argparse.ArgumentParser();p.add_argument('--release',type=Path,required=True);p.add_argument('--release-qa',type=Path,required=True);p.add_argument('--verify-only',action='store_true');a=p.parse_args()
 if a.verify_only:r,plan=validate(a.release,a.release_qa);print(json.dumps({'valid':True,'planned':len(plan['results'])},indent=2));return 0
 r=execute(a.release,a.release_qa);print(json.dumps({k:r[k] for k in ('status','network_request_count','captured_count','quarantined_count','failed_count','not_attempted_count')},indent=2));return 0 if r['status'].startswith('COMPLETE') else 2
if __name__=='__main__':raise SystemExit(main())
