"""Verify the finite Lane A public-metadata gap-resolution release."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "target_text_corpus_v1_public_metadata_gap_resolution_release_v1.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(require_output_absent: bool = False) -> dict:
    value = json.loads(RELEASE.read_text(encoding="utf-8"))
    for item in value["inputs"]:
        target = ROOT / item["path"]
        if not target.is_file() or sha256_file(target) != item["sha256"]:
            raise ValueError(f"Input hash mismatch: {item['path']}")
    tasks = value["tasks"]
    if [task["task_id"] for task in tasks] != ["A01","A02","A03","A04"]:
        raise ValueError("Exact Lane A task order changed")
    pages = [page for task in tasks for page in task["pages"]]
    if len(pages) != 7 or len(set(pages)) != 7:
        raise ValueError("Release must contain exactly seven new unique pages")
    contract = value["execution_contract"]
    if any(urlparse(page).hostname not in contract["allowed_authorities"] for page in pages):
        raise ValueError("Page authority outside allowlist")
    if contract["maximum_search_queries"] != 1 or contract["maximum_non_pdf_page_reads"] != 8 or contract["maximum_pdf_pages_inspected"] != 24:
        raise ValueError("Release bounds changed")
    if contract["maximum_total_read_operations"] != 32 or contract["identical_prior_query_or_page_retry_allowed"] is not False:
        raise ValueError("Read or anti-repeat policy changed")
    for key in (
        "dataset_download_allowed","repository_clone_allowed","dataset_record_open_allowed","csv_or_jsonl_open_allowed",
        "raw_html_retention_allowed","candidate_live_domain_access_allowed","gated_condition_acceptance_allowed",
        "author_contact_allowed","code_execution_allowed","labeling_allowed","validation_or_test_open_allowed","model_operations_allowed",
    ):
        if contract[key] is not False:
            raise ValueError(f"Closed capability opened: {key}")
    if contract["no_overwrite"] is not True or contract["unresolved_policy"] != "RETAIN_UNRESOLVED_NO_INFERENCE":
        raise ValueError("Fail-closed policy changed")
    output = ROOT / value["planned_output"]
    if require_output_absent and output.exists():
        raise FileExistsError(output)
    return {"status":"PASS_PUBLIC_METADATA_GAP_RELEASE_VERIFIED","tasks":4,"pages":7,"queries":1,"output_exists":output.exists()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify(args.verify_only), ensure_ascii=False))
