"""Verify the exact-42 continuation plan by full recomputation."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from scripts.build_target_text_corpus_v1_ready_channel_capture_continuation_plan_v1 import load,sha256_file
from scripts.build_target_text_corpus_v1_ready_channel_capture_continuation_plan_v3 import build
def verify(path:Path):
 p=load(path);i=p['inputs'];e=build(Path(i['parent_plan']['path']),Path(i['parent_report']['path']),Path(i['parent_result_qa']['path']));errs=[] if p==e else ['recomputation mismatch'];ids=[x['availability_plan_id'] for x in p.get('results',[])]
 if len(ids)!=42 or len(set(ids))!=42 or {'TTCV1_B3_AVAIL_009','TTCV1_B3_AVAIL_010','TTCV1_B3_AVAIL_020'}&set(ids):errs.append('membership changed')
 return {'verification_id':'ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_CAPTURE_CONTINUATION_PLAN_QA_V3','status':'PASS_EXACT_42_NEVER_ATTEMPTED_CONTINUATION_PLAN' if not errs else 'FAIL','plan':{'path':str(path.resolve()),'sha256':sha256_file(path)},'checks':{'planned':len(ids),'full_recomputation_match':not errs},'decision':{'release_may_be_prepared':not errs,'capture_execution_authorized':False,'labeling_allowed':False,'training_allowed':False},'errors':errs}
def main():
 p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise FileExistsError(a.output)
 v=verify(a.plan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(v,indent=2)+'\n');print(json.dumps(v,indent=2));return 0 if not v['errors'] else 1
if __name__=='__main__':raise SystemExit(main())
