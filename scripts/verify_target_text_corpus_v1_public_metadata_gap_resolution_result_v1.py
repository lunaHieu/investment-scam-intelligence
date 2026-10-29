"""Verify the fail-closed Lane A result and protocol-stop accounting."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.verify_target_text_corpus_v1_public_metadata_gap_resolution_release_v1 import RELEASE, verify as verify_release


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "registry" / "analyses" / "target_text_corpus_v1_public_metadata_gap_resolution_result_v1.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify() -> dict:
    release_check = verify_release()
    if release_check["status"] != "PASS_PUBLIC_METADATA_GAP_RELEASE_VERIFIED":
        raise ValueError("Release verification failed")
    value = json.loads(RESULT.read_text(encoding="utf-8"))
    inputs = {item["role"]: item for item in value["inputs"]}
    if inputs["release"]["sha256"] != sha256_file(RELEASE):
        raise ValueError("Release hash mismatch")
    qa_path = ROOT / inputs["release_qa"]["path"]
    if inputs["release_qa"]["sha256"] != sha256_file(qa_path):
        raise ValueError("Release QA hash mismatch")
    execution = value["execution"]
    if execution["query_ids_executed"] != ["PMQ01"] or execution["search_queries_executed"] != 1:
        raise ValueError("Query accounting mismatch")
    if (execution["page_reads_attempted"], execution["page_reads_succeeded"], execution["page_read_errors"]) != (7, 1, 6):
        raise ValueError("Page-read accounting mismatch")
    if execution["automatic_dataset_record_preview_exposures"] != 1 or execution["dataset_preview_used_as_evidence"] is not False:
        raise ValueError("Forbidden preview exposure is not fail-closed")
    for key in ("source_files_downloaded","repositories_cloned","raw_html_files_retained","candidate_live_domain_access_operations","gated_conditions_accepted","author_contacts","labels_created","validation_or_test_rows_used","model_operations"):
        if execution[key] != 0:
            raise ValueError(f"Unexpected side effect: {key}")
    if [item["task_id"] for item in value["task_results"]] != ["A01","A02","A03","A04"]:
        raise ValueError("Task identity changed")
    if any(item["retry_same_page_allowed"] is not False for item in value["task_results"]):
        raise ValueError("Identical retry was left open")
    if value["evidence_state_changes"] != [] or value["summary"]["validly_advanced_tasks"] != 0:
        raise ValueError("Invalid execution changed evidence state")
    decision = value["decision"]
    if decision["release_consumed_never_rerun"] is not True or decision["same_page_retry_allowed"] is not False:
        raise ValueError("Consumed release can be rerun")
    if decision["dataset_acquisition_allowed"] is not False or decision["training_allowed"] is not False:
        raise ValueError("Closed gate opened")
    return {"status":"PASS_FAIL_CLOSED_RESULT_VERIFIED","tasks":4,"validly_advanced":0,"preview_exposure_pages":1,"files_acquired":0}


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False))
