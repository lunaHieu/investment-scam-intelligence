"""Crash-safe V2 HEAD-only endpoint assessment with incremental journaling."""

from __future__ import annotations

import argparse, hashlib, json, time, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RELEASE=ROOT/"configs"/"target_text_corpus_v1_record_free_endpoint_assessment_release_v2.json"

def sha256_file(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):return None
def _write_atomic(path:Path,value:dict)->None:
 temp=path.with_suffix(path.suffix+".tmp");temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8");temp.replace(path)
def _headers(headers):return {k:headers.get(k) for k in ("Content-Type","Content-Length","Location","ETag","Last-Modified","Server","Date")}
def verify_release(require_absent:bool=False)->dict:
 v=json.loads(RELEASE.read_text(encoding="utf-8"))
 for i in v["inputs"]:
  p=ROOT/i["path"]
  if not p.is_file() or sha256_file(p)!=i["sha256"]:raise ValueError(f"Input hash mismatch: {i['path']}")
 source=json.loads((ROOT/v["endpoints_source"]).read_text(encoding="utf-8"));ids=[e["endpoint_id"] for e in source["endpoints"]]
 if ids!=v["endpoint_ids"] or len(ids)!=8:raise ValueError("Endpoint identity changed")
 c=v["execution_contract"]
 if c["exact_head_requests"]!=8 or c["minimum_seconds_between_requests"]<2:raise ValueError("Bounds changed")
 for k in ("follow_redirects","response_body_read_allowed","response_body_retention_allowed","get_requests_allowed","dataset_landing_or_viewer_pages_allowed","dataset_download_allowed","repository_clone_allowed","candidate_live_domain_access_allowed","auto_resume_allowed"):
  if c[k] is not False:raise ValueError(f"Closed capability opened: {k}")
 for k in ("incremental_journal_after_each_request","atomic_journal_replacement","result_assembly_smoke_test_required","no_overwrite"):
  if c[k] is not True:raise ValueError(f"Required safeguard removed: {k}")
 out,part=ROOT/v["planned_output"],ROOT/v["planned_partial"]
 if require_absent and (out.exists() or part.exists()):raise FileExistsError("V2 output exists")
 return {"status":"PASS_RECORD_FREE_ENDPOINT_V2_RELEASE_VERIFIED","endpoints":8,"output_exists":out.exists(),"partial_exists":part.exists()}
def assemble_result(rows:list[dict],release_sha:str)->dict:
 return {"analysis_id":"ISI_TARGET_TEXT_CORPUS_V1_RECORD_FREE_ENDPOINT_ASSESSMENT_RESULT_V2","created_at":datetime.now(timezone.utc).isoformat(),"status":"IMMUTABLE_HEAD_ONLY_ENDPOINT_ASSESSMENT_REQUIRES_QA","release_path":"configs/target_text_corpus_v1_record_free_endpoint_assessment_release_v2.json","release_sha256":release_sha,"method":"HEAD","requests_attempted":len(rows),"response_bodies_read":0,"response_bodies_retained":0,"results":rows,"decision":{"content_get_release_allowed":False,"dataset_acquisition_allowed":False,"training_allowed":False},"safety_contract":{"network_operations":0,"metadata_head_requests":len(rows),"project_data_network_acquisition_operations":0,"source_files_acquired":0,"candidate_domain_access_operations":0,"labels_created":0,"training_allowed":False}}
def execute()->dict:
 verify_release(True);v=json.loads(RELEASE.read_text(encoding="utf-8"));source=json.loads((ROOT/v["endpoints_source"]).read_text(encoding="utf-8"));out,part=ROOT/v["planned_output"],ROOT/v["planned_partial"];part.parent.mkdir(parents=True,exist_ok=True);release_sha=sha256_file(RELEASE);rows=[];_write_atomic(part,{"status":"RESERVED_BEFORE_NETWORK","release_sha256":release_sha,"attempts_completed":0,"results":rows});opener=urllib.request.build_opener(NoRedirect)
 for n,e in enumerate(source["endpoints"]):
  if n:time.sleep(v["execution_contract"]["minimum_seconds_between_requests"])
  req=urllib.request.Request(e["url"],method="HEAD",headers={"User-Agent":"investment-scam-intelligence-record-free-endpoint-assessment/2.0"});row={"endpoint_id":e["endpoint_id"],"url":e["url"]}
  try:
   with opener.open(req,timeout=30) as r:row.update({"status_code":r.status,**_headers(r.headers),"error_type":None,"error_message":None})
  except urllib.error.HTTPError as x:row.update({"status_code":x.code,**_headers(x.headers),"error_type":"HTTPError","error_message":str(x.reason)})
  except Exception as x:row.update({"status_code":None,"Content-Type":None,"Content-Length":None,"Location":None,"ETag":None,"Last-Modified":None,"Server":None,"Date":None,"error_type":type(x).__name__,"error_message":str(x)})
  rows.append(row);_write_atomic(part,{"status":"IN_PROGRESS","release_sha256":release_sha,"attempts_completed":len(rows),"results":rows})
 result=assemble_result(rows,release_sha);_write_atomic(out,result);part.unlink();return result
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--verify-only",action="store_true");p.add_argument("--smoke-result-assembly",action="store_true");a=p.parse_args()
 if a.smoke_result_assembly:print(json.dumps(assemble_result([],"0"*64),ensure_ascii=False))
 else:print(json.dumps(verify_release(a.verify_only) if a.verify_only else execute(),ensure_ascii=False))
