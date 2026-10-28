"""Build the exact-42 never-attempted capture continuation plan."""
from __future__ import annotations
import argparse,json
from collections import Counter
from pathlib import Path
from scripts.build_target_text_corpus_v1_ready_channel_capture_continuation_plan_v1 import load,sha256_file
def build(parent:Path,reportp:Path,qap:Path):
 p,r,q=load(parent),load(reportp),load(qap)
 if p.get('status')!='FROZEN_EXACT_48_NEVER_ATTEMPTED_ONLY_CAPTURE_PLAN':raise ValueError('parent plan changed')
 if (r.get('captured_count'),r.get('failed_provider_or_transport_count'),r.get('not_attempted_count'))!=(5,1,42):raise ValueError('parent result changed')
 if q.get('status')!='PASS_PARTIAL_PROVIDER_FAILURE_PRESERVED' or q['inputs']['report_sha256']!=sha256_file(reportp):raise ValueError('parent QA mismatch')
 byid={x['capture_plan_id']:x for x in p['results']};rows=[byid[x['capture_plan_id']] for x in r['results'] if x['outcome']=='NOT_ATTEMPTED_AFTER_PROVIDER_ERROR_STOP']
 if len(rows)!=42 or any(Path(x['capture_path']).exists() for x in rows):raise ValueError('exact-42 state changed')
 forbidden={'TTCV1_B3_AVAIL_009','TTCV1_B3_AVAIL_010','TTCV1_B3_AVAIL_020'}
 if forbidden&{x['availability_plan_id'] for x in rows}:raise ValueError('quarantine leaked')
 return {'plan_id':'ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_CAPTURE_CONTINUATION_PLAN_V3','status':'FROZEN_EXACT_42_NEVER_ATTEMPTED_ONLY_CAPTURE_PLAN','inputs':{'parent_plan':{'path':str(parent.resolve()),'sha256':sha256_file(parent)},'parent_report':{'path':str(reportp.resolve()),'sha256':sha256_file(reportp)},'parent_result_qa':{'path':str(qap.resolve()),'sha256':sha256_file(qap)}},'planned_capture_count':42,'planned_by_cohort':dict(Counter(x['cohort'] for x in rows)),'excluded_quarantined_rows':sorted(forbidden),'results':rows,'decision':{'release_may_be_prepared':False,'capture_execution_authorized':False,'candidate_live_domain_access_allowed':False,'labeling_allowed':False,'training_allowed':False}}
def main():
 a=argparse.ArgumentParser();a.add_argument('--parent-plan',type=Path,required=True);a.add_argument('--parent-report',type=Path,required=True);a.add_argument('--parent-result-qa',type=Path,required=True);a.add_argument('--output',type=Path,required=True);x=a.parse_args()
 if x.output.exists():raise FileExistsError(x.output)
 v=build(x.parent_plan,x.parent_report,x.parent_result_qa);x.output.parent.mkdir(parents=True,exist_ok=True);x.output.write_text(json.dumps(v,indent=2)+'\n');print(json.dumps({'status':v['status'],'planned':42,'sha256':sha256_file(x.output)},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
