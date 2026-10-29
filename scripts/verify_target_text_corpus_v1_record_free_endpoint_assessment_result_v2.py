"""Verify V2 HEAD-only endpoint assessment without opening any endpoint."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];RESULT=ROOT/"registry"/"analyses"/"target_text_corpus_v1_record_free_endpoint_assessment_result_v2.json";RELEASE=ROOT/"configs"/"target_text_corpus_v1_record_free_endpoint_assessment_release_v2.json";SOURCE=ROOT/"configs"/"target_text_corpus_v1_record_free_endpoint_assessment_release_v1.json"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify():
 v=json.loads(RESULT.read_text(encoding="utf-8"));r=json.loads(RELEASE.read_text(encoding="utf-8"));s=json.loads(SOURCE.read_text(encoding="utf-8"))
 if v["release_sha256"]!=sha(RELEASE):raise ValueError("Release hash mismatch")
 if v["method"]!="HEAD" or v["requests_attempted"]!=8 or v["response_bodies_read"]!=0 or v["response_bodies_retained"]!=0:raise ValueError("HEAD/body contract mismatch")
 rows=v["results"]
 if [x["endpoint_id"] for x in rows]!=r["endpoint_ids"] or [x["url"] for x in rows]!=[x["url"] for x in s["endpoints"]]:raise ValueError("Endpoint identity mismatch")
 if [x["status_code"] for x in rows].count(200)!=7 or [x["status_code"] for x in rows].count(307)!=1:raise ValueError("Unexpected status accounting")
 allowed=("application/json","text/plain","application/pdf")
 if any(not str(x["Content-Type"]).startswith(allowed) for x in rows):raise ValueError("Unexpected content type")
 if any(x["endpoint_id"]!="RFE07" and x["error_type"] is not None for x in rows):raise ValueError("Unexpected endpoint error")
 if rows[6]["status_code"]!=307 or "a90e2bd7e8df2376939658075ba8094dcee488ad" not in str(rows[6]["Location"]):raise ValueError("Immutable redirect identity missing")
 if v["decision"]["content_get_release_allowed"] is not False or v["decision"]["training_allowed"] is not False:raise ValueError("Gate opened")
 return {"status":"PASS_HEAD_ONLY_RESULT_V2_VERIFIED","endpoints":8,"http_200":7,"http_307":1,"response_bodies_read":0,"content_get_authorized":0}
if __name__=="__main__":print(json.dumps(verify(),ensure_ascii=False))
