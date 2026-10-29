"""Verify the immutable bounded source-discovery result."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "registry" / "analyses" / "target_text_corpus_v1_sanitized_text_source_discovery_result_v1.json"


def verify_result(path: Path = RESULT) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    for item in value["inputs"]:
        target = ROOT / item["path"]
        if hashlib.sha256(target.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"Input hash mismatch: {item['path']}")
    execution = value["execution"]
    if execution["query_ids_executed"] != [f"Q{index:02d}" for index in range(1, 13)]:
        raise ValueError("Query identity/order mismatch")
    if execution["search_queries_executed"] != 12:
        raise ValueError("Query count mismatch")
    for key in ("source_files_downloaded", "candidate_live_domain_access_operations", "raw_html_files_retained", "labels_created", "model_operations"):
        if execution[key] != 0:
            raise ValueError(f"Forbidden execution occurred: {key}")
    candidates = value["candidates"]
    if len(candidates) > 20 or len({item["candidate_id"] for item in candidates}) != len(candidates):
        raise ValueError("Candidate count or identity invalid")
    required = {"candidate_id","publisher","landing_url","format_claim","license_or_terms_url","observed_text_claim","provenance_claim","language_claim","role_claim","risks","disposition","evidence_urls"}
    if any(set(item) != required for item in candidates):
        raise ValueError("Candidate schema mismatch")
    summary = value["summary"]
    if summary["shortlisted_for_independent_second_review"] != 6:
        raise ValueError("Shortlist count mismatch")
    decision = value["decision"]
    if decision["independent_second_review_required"] is not True or decision["acquisition_release_may_be_prepared"] is not False:
        raise ValueError("Review/acquisition gate changed")
    for key in ("downloads_allowed", "candidate_live_domain_access_allowed", "labeling_allowed", "training_allowed"):
        if decision[key] is not False:
            raise ValueError(f"Safety gate opened: {key}")
    return {"status":"PASS_PRELIMINARY_RESULT_REQUIRES_SECOND_REVIEW","candidate_count":len(candidates),"shortlist_count":6}


def main() -> None:
    print(json.dumps(verify_result(), ensure_ascii=False))


if __name__ == "__main__":
    main()
