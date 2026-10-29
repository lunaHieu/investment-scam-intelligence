"""Verify or execute the exact HEAD-only record-free endpoint assessment."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "target_text_corpus_v1_record_free_endpoint_assessment_release_v1.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def verify_release(require_outputs_absent: bool = False) -> dict:
    value = json.loads(RELEASE.read_text(encoding="utf-8"))
    for item in value["inputs"]:
        target = ROOT / item["path"]
        if not target.is_file() or sha256_file(target) != item["sha256"]:
            raise ValueError(f"Input hash mismatch: {item['path']}")
    endpoints = value["endpoints"]
    if [item["endpoint_id"] for item in endpoints] != [f"RFE{i:02}" for i in range(1, 9)]:
        raise ValueError("Exact endpoint identity/order changed")
    if any(item["method"] != "HEAD" for item in endpoints):
        raise ValueError("Non-HEAD method present")
    contract = value["execution_contract"]
    if contract["exact_head_requests"] != 8 or contract["minimum_seconds_between_requests"] < 2:
        raise ValueError("Request bound or pacing changed")
    for key in ("follow_redirects","response_body_read_allowed","response_body_retention_allowed","dataset_landing_or_viewer_pages_allowed","get_requests_allowed","dataset_download_allowed","repository_clone_allowed","raw_html_retention_allowed","candidate_live_domain_access_allowed","author_contact_allowed","labeling_allowed","validation_or_test_open_allowed","model_operations_allowed","auto_resume_allowed"):
        if contract[key] is not False:
            raise ValueError(f"Closed capability opened: {key}")
    if contract["no_overwrite"] is not True or contract["partial_journal_required"] is not True:
        raise ValueError("Crash-safe no-overwrite policy changed")
    output, partial = ROOT / value["planned_output"], ROOT / value["planned_partial"]
    if require_outputs_absent and (output.exists() or partial.exists()):
        raise FileExistsError("Final or partial output already exists")
    return {"status":"PASS_RECORD_FREE_ENDPOINT_RELEASE_VERIFIED","endpoints":8,"method":"HEAD","output_exists":output.exists(),"partial_exists":partial.exists()}


def _headers(headers) -> dict:
    return {key: headers.get(key) for key in ("Content-Type","Content-Length","Location","ETag","Last-Modified","Server","Date")}


def execute() -> dict:
    check = verify_release(require_outputs_absent=True)
    value = json.loads(RELEASE.read_text(encoding="utf-8"))
    output, partial = ROOT / value["planned_output"], ROOT / value["planned_partial"]
    partial.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text(json.dumps({"status":"RESERVED_BEFORE_NETWORK","release_sha256":sha256_file(RELEASE)}, separators=(",",":")), encoding="utf-8")
    opener = urllib.request.build_opener(NoRedirect)
    results = []
    delay = value["execution_contract"]["minimum_seconds_between_requests"]
    for index, endpoint in enumerate(value["endpoints"]):
        if index:
            time.sleep(delay)
        request = urllib.request.Request(endpoint["url"], method="HEAD", headers={"User-Agent":"investment-scam-intelligence-record-free-endpoint-assessment/1.0"})
        row = {"endpoint_id":endpoint["endpoint_id"],"url":endpoint["url"]}
        try:
            with opener.open(request, timeout=30) as response:
                row.update({"status_code":response.status,**_headers(response.headers),"error_type":None,"error_message":None})
        except urllib.error.HTTPError as error:
            row.update({"status_code":error.code,**_headers(error.headers),"error_type":"HTTPError","error_message":str(error.reason)})
        except Exception as error:
            row.update({"status_code":None,"Content-Type":None,"Content-Length":None,"Location":None,"ETag":None,"Last-Modified":None,"Server":None,"Date":None,"error_type":type(error).__name__,"error_message":str(error)})
        results.append(row)
    result = {
        "analysis_id":"ISI_TARGET_TEXT_CORPUS_V1_RECORD_FREE_ENDPOINT_ASSESSMENT_RESULT_V1",
        "created_at":datetime.now(timezone.utc).isoformat(),
        "status":"IMMUTABLE_HEAD_ONLY_ENDPOINT_ASSESSMENT_REQUIRES_QA",
        "release_path":"configs/target_text_corpus_v1_record_free_endpoint_assessment_release_v1.json",
        "release_sha256":sha256_file(RELEASE),
        "method":"HEAD","requests_attempted":8,"response_bodies_read":0,"response_bodies_retained":0,
        "results":results,
        "decision":{"content_get_release_allowed":false,"dataset_acquisition_allowed":false,"training_allowed":false},
        "safety_contract":{"network_operations":0,"metadata_head_requests":8,"project_data_network_acquisition_operations":0,"source_files_acquired":0,"candidate_domain_access_operations":0,"labels_created":0,"training_allowed":false}
    }
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    partial.unlink()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify_release(args.verify_only) if args.verify_only else execute(), ensure_ascii=False))
