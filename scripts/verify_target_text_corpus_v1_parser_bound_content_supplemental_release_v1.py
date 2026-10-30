"""Verify the exact PBC05-PBC08 supplemental release without network access."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.verify_target_text_corpus_v1_parser_bound_content_result_v1 import verify_result
from scripts.verify_target_text_corpus_v1_parser_bound_content_release_v1 import RELEASE as V1_RELEASE, ROOT


RELEASE = ROOT / "configs" / "target_text_corpus_v1_parser_bound_content_supplemental_release_v1.json"
PASS_STATUS = "PASS_EXACT_PBC05_PBC08_SUPPLEMENTAL_RELEASE_EXECUTION_CLOSED"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(path: Path = RELEASE) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if value.get("status") != "FROZEN_PREPARATION_EXECUTION_CLOSED":
        errors.append("Supplemental release status changed")
    inputs = {item["role"]: item for item in value.get("inputs", [])}
    for role, item in inputs.items():
        target = ROOT / str(item.get("path", ""))
        if not target.is_file() or sha256_file(target) != item.get("sha256"):
            errors.append(f"Pinned supplemental input mismatch: {role}")
    result_path = ROOT / str(inputs.get("immutable_v1_result", {}).get("path", ""))
    if result_path.is_file():
        try:
            verified = verify_result(result_path)
            if verified.get("status") != "PASS_PARSER_BOUND_CONTENT_RESULT_VERIFIED":
                errors.append("V1 result no longer verifies")
        except Exception as error:
            errors.append(f"V1 result verification failed: {type(error).__name__}")
    v1 = json.loads(V1_RELEASE.read_text(encoding="utf-8"))
    expected_ids = ["PBC05", "PBC06", "PBC07", "PBC08"]
    if value.get("resource_ids") != expected_ids:
        errors.append("Supplemental population changed")
    v1_ids = [item["resource_id"] for item in v1["resources"]]
    if [item for item in v1_ids if item in expected_ids] != expected_ids:
        errors.append("Supplemental order no longer matches V1")
    contract = value.get("execution_contract", {})
    if contract.get("maximum_get_requests") != 4 or contract.get("maximum_attempts_per_resource") != 1:
        errors.append("Supplemental request bound changed")
    for key in (
        "repeat_pbc01_through_pbc04_allowed", "raw_response_retention_allowed",
        "automatic_retry_allowed", "automatic_resume_allowed",
        "candidate_live_domain_access_allowed", "dataset_file_download_allowed",
        "pdf_diagnostic_text_retention_allowed",
    ):
        if contract.get(key) is not False:
            errors.append(f"Forbidden supplemental behavior opened: {key}")
    for key in (
        "no_overwrite", "continue_after_row_local_parser_failure", "stop_on_transport_error",
        "stop_on_provider_http_error", "pdf_visual_review_required_before_evidence_acceptance",
    ):
        if contract.get(key) is not True:
            errors.append(f"Required supplemental safeguard missing: {key}")
    decision = value.get("decision", {})
    if decision.get("release_prepared") is not True:
        errors.append("Supplemental release is not prepared")
    for key in (
        "network_execution_allowed_now", "evidence_acceptance_allowed", "labeling_allowed",
        "validation_or_test_opening_allowed", "model_operations_allowed", "training_allowed",
    ):
        if decision.get(key) is not False:
            errors.append(f"Supplemental release opened a forbidden gate: {key}")
    output = ROOT / value["planned_output"]
    partial = ROOT / value["planned_partial"]
    outputs_absent = not output.exists() and not partial.exists() and not Path(str(partial) + ".tmp").exists()
    if not outputs_absent:
        errors.append("Supplemental output already exists")
    return {
        "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_PARSER_BOUND_CONTENT_SUPPLEMENTAL_RELEASE_QA_V1",
        "status": PASS_STATUS if not errors else "FAIL",
        "release": {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256_file(path)},
        "checks": {
            "resource_ids": value.get("resource_ids"),
            "maximum_get_requests": contract.get("maximum_get_requests"),
            "continue_after_row_local_parser_failure": contract.get("continue_after_row_local_parser_failure"),
            "outputs_absent": outputs_absent,
        },
        "decision": {"release_verified": not errors, "network_execution_allowed_now": False, "training_allowed": False},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "labels_created": 0, "model_operations": 0},
    }


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
