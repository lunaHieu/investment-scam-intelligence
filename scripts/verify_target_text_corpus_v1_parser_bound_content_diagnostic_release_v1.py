"""Verify the exact two-row diagnostic preparation without network access."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "target_text_corpus_v1_parser_bound_content_diagnostic_release_v1.json"
QA = ROOT / "registry" / "analyses" / "target_text_corpus_v1_parser_bound_content_diagnostic_release_qa_v1.json"
OLD_RESULT = ROOT / "registry" / "analyses" / "target_text_corpus_v1_parser_bound_content_supplemental_result_v1.json"
OLD_RESULT_SHA256 = "e4b351618437205d0cf688bbf5656fbd0f0250c8fcb62a0e2a97330a2796d17a"
EXPECTED_IDS = ["PBC05", "PBC08"]
PASS_STATUS = "PASS_EXACT_TWO_ROW_DIAGNOSTIC_RELEASE_PREPARED_EXECUTION_CLOSED"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify() -> dict:
    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    errors: list[str] = []
    if release.get("status") != "FROZEN_PREPARATION_EXECUTION_CLOSED":
        errors.append("Release is not frozen and execution-closed")
    if [item.get("resource_id") for item in release.get("resources", [])] != EXPECTED_IDS:
        errors.append("Population/order must be exactly PBC05, PBC08")
    input_roles = {item.get("role"): item for item in release.get("inputs", [])}
    for item in release.get("inputs", []):
        path = ROOT / str(item.get("path", ""))
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            errors.append(f"Pinned input mismatch: {item.get('role')}")
    if not OLD_RESULT.is_file() or sha256_file(OLD_RESULT) != OLD_RESULT_SHA256:
        errors.append("Immutable four-row result is missing or changed")
    if input_roles.get("immutable_supplemental_result", {}).get("sha256") != OLD_RESULT_SHA256:
        errors.append("Release does not pin the completed supplemental result")

    allowed_hosts = {"aclanthology.org", "huggingface.co"}
    for row in release.get("resources", []):
        if urlparse(str(row.get("url", ""))).hostname not in allowed_hosts:
            errors.append(f"Unexpected source host: {row.get('resource_id')}")
        if row.get("raw_response_retention_allowed") is not False:
            errors.append(f"Raw response retention opened: {row.get('resource_id')}")
    pbc05, pbc08 = release.get("resources", [{}, {}])
    if pbc05.get("diagnostic_code_allowlist") != [
        "PDF_INVALID_MAGIC", "PDF_OPEN_OR_PARSE_ERROR", "PDF_PAGE_LIMIT_EXCEEDED",
        "PDF_PAGE_TEXT_EXTRACTION_ERROR", "PDF_EXTRACTION_RUNTIME_ERROR",
    ]:
        errors.append("PBC05 diagnostic allowlist changed")
    if pbc08.get("diagnostic_code_allowlist") != [
        "FORBIDDEN_DATASET_KEY_PRESENT", "COMMIT_LIST_MISSING_OR_INVALID",
        "COMMIT_ENTRY_NOT_OBJECT", "COMMIT_ID_INVALID",
    ]:
        errors.append("PBC08 diagnostic allowlist changed")
    contract = release.get("execution_contract", {})
    if contract.get("maximum_get_requests") != 2 or contract.get("maximum_attempts_per_resource") != 1:
        errors.append("Request bound changed")
    for key in (
        "repeat_pbc01_through_pbc04_allowed", "repeat_pbc06_pbc07_allowed",
        "repeat_diagnostic_release_allowed", "automatic_retry_allowed",
        "automatic_resume_allowed", "archive_download_allowed",
        "dataset_file_download_allowed", "raw_response_retention_allowed",
        "candidate_live_domain_access_allowed", "validation_or_test_open_allowed",
        "model_operations_allowed", "training_allowed",
    ):
        if contract.get(key) is not False:
            errors.append(f"Forbidden capability opened: {key}")
    if contract.get("minimum_request_interval_seconds", 0) < 30 or contract.get("timeout_seconds") != 30:
        errors.append("HTTP pacing/timeout bounds weakened")
    decision = release.get("decision", {})
    for key in (
        "network_execution_allowed_now", "evidence_acceptance_allowed",
        "dataset_acquisition_allowed", "labeling_allowed", "training_allowed",
    ):
        if decision.get(key) is not False:
            errors.append(f"Decision gate opened: {key}")
    output = ROOT / str(release.get("planned_output", ""))
    partial = ROOT / str(release.get("planned_partial", ""))
    if output.exists() or partial.exists() or Path(str(partial) + ".tmp").exists():
        errors.append("Planned output state already exists")
    return {
        "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_PARSER_BOUND_CONTENT_DIAGNOSTIC_RELEASE_QA_V1",
        "status": PASS_STATUS if not errors else "FAIL",
        "release": {"path": RELEASE.relative_to(ROOT).as_posix(), "sha256": sha256_file(RELEASE)},
        "checks": {
            "resource_ids": EXPECTED_IDS,
            "maximum_get_requests": contract.get("maximum_get_requests"),
            "minimum_request_interval_seconds": contract.get("minimum_request_interval_seconds"),
            "old_result_hash_verified": OLD_RESULT.is_file() and sha256_file(OLD_RESULT) == OLD_RESULT_SHA256,
            "planned_outputs_absent": not output.exists() and not partial.exists() and not Path(str(partial) + ".tmp").exists(),
        },
        "decision": {
            "release_verified": not errors,
            "network_execution_allowed_now": False,
            "separate_owner_execution_authorization_required": True,
            "training_allowed": False,
        },
        "errors": errors,
        "safety_contract": {"network_operations": 0, "raw_responses_retained": 0, "labels_created": 0, "model_operations": 0},
    }


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
