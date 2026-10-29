"""Independently recompute invariants of Metadata Evidence Result V1."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from scripts.verify_target_text_corpus_v1_metadata_evidence_release_v1 import DEFAULT_RELEASE, verify_release


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULT = ROOT / "registry" / "analyses" / "target_text_corpus_v1_metadata_evidence_result_v1.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_result(path: Path = DEFAULT_RESULT) -> dict:
    release_check = verify_release(DEFAULT_RELEASE)
    if release_check["status"] != "PASS_METADATA_EVIDENCE_RELEASE_VERIFIED":
        raise ValueError("Release verification failed")
    release = json.loads(DEFAULT_RELEASE.read_text(encoding="utf-8"))
    result = json.loads(path.read_text(encoding="utf-8"))
    inputs = {item["role"]: item for item in result["inputs"]}
    if inputs["release"]["sha256"] != sha256_file(DEFAULT_RELEASE):
        raise ValueError("Result release hash mismatch")
    release_qa = ROOT / inputs["release_qa"]["path"]
    if not release_qa.is_file() or inputs["release_qa"]["sha256"] != sha256_file(release_qa):
        raise ValueError("Result release-QA hash mismatch")

    expected = {
        branch["branch_id"]: [item["evidence_id"] for item in branch["evidence_items"]]
        for branch in release["branches"]
    }
    actual_branches = result["branches"]
    if [branch["branch_id"] for branch in actual_branches] != list(expected):
        raise ValueError("Result branch order or identity changed")
    items = []
    for branch in actual_branches:
        actual_ids = [item["evidence_id"] for item in branch["evidence_items"]]
        if actual_ids != expected[branch["branch_id"]]:
            raise ValueError(f"Evidence order changed for {branch['branch_id']}")
        if branch["acquisition_ready"] is not False:
            raise ValueError("Metadata result cannot open acquisition")
        source_urls = {source["url"] for source in branch["evidence_sources"]}
        for item in branch["evidence_items"]:
            if item["status"] not in {"RESOLVED", "PARTIAL", "UNRESOLVED"}:
                raise ValueError(f"Unknown evidence status: {item['status']}")
            if item["inference_from_absence"] is not False:
                raise ValueError("Evidence item inferred a fact from absence")
            if not item["supporting_urls"] or not set(item["supporting_urls"]).issubset(source_urls):
                raise ValueError(f"Unsupported evidence URLs: {item['evidence_id']}")
            for url in item["supporting_urls"]:
                if urlparse(url).hostname not in release["execution_contract"]["allowed_authorities"]:
                    raise ValueError(f"Evidence authority not allowed: {url}")
            items.append(item)

    counts = Counter(item["status"].lower() for item in items)
    summary = result["summary"]
    recomputed = {
        "branches":len(actual_branches), "evidence_items":len(items),
        "resolved":counts["resolved"], "partial":counts["partial"], "unresolved":counts["unresolved"],
    }
    for key, value in recomputed.items():
        if summary[key] != value:
            raise ValueError(f"Summary mismatch: {key}")
    if summary["fresh_v1_core_credit"] != 0 or summary["new_training_rows_authorized"] != 0:
        raise ValueError("Metadata result created data or training credit")

    execution = result["execution"]
    if execution["query_ids_executed"] != [item["query_id"] for item in release["metadata_queries"]]:
        raise ValueError("Executed query identities changed")
    if execution["search_queries_executed"] != 6 or execution["page_reads_attempted"] != 18:
        raise ValueError("Execution bounds or counts changed")
    if execution["page_reads_succeeded"] + execution["page_read_errors"] != execution["page_reads_attempted"]:
        raise ValueError("Page-read accounting mismatch")
    if any(execution[key] != 0 for key in (
        "source_files_downloaded", "repositories_cloned", "raw_dataset_files_opened",
        "raw_html_files_retained", "candidate_live_domain_access_operations", "author_contacts",
        "labels_created", "validation_or_test_rows_opened", "model_operations",
    )):
        raise ValueError("Forbidden execution side effect recorded")
    if result["decision"]["any_acquisition_release_may_be_prepared"] is not False:
        raise ValueError("Acquisition gate was opened")
    safety = result["safety_contract"]
    if safety["project_data_network_acquisition_operations"] != 0 or safety["source_files_acquired"] != 0:
        raise ValueError("Project data was acquired")
    if safety["training_allowed"] is not False:
        raise ValueError("Training gate was opened")
    return {"status":"PASS_METADATA_EVIDENCE_RESULT_VERIFIED", **recomputed, "acquisition_ready_sources":0}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    args = parser.parse_args()
    print(json.dumps(verify_result(args.result), ensure_ascii=False))


if __name__ == "__main__":
    main()
