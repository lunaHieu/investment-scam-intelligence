"""Verify supplemental authorization protocol and an optional owner amendment."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.verify_target_text_corpus_v1_parser_bound_content_release_v1 import ROOT
from scripts.verify_target_text_corpus_v1_parser_bound_content_supplemental_release_v1 import (
    PASS_STATUS as RELEASE_PASS,
    verify as verify_release,
)


PROTOCOL = ROOT / "configs" / "target_text_corpus_v1_parser_bound_content_supplemental_execution_authorization_protocol_v1.json"
AMENDMENT = ROOT / "configs" / "target_text_corpus_v1_parser_bound_content_supplemental_execution_amendment_v1.json"
AMENDMENT_QA = ROOT / "registry" / "analyses" / "target_text_corpus_v1_parser_bound_content_supplemental_execution_amendment_qa_v1.json"
RELEASE_QA = ROOT / "registry" / "analyses" / "target_text_corpus_v1_parser_bound_content_supplemental_release_qa_v1.json"
PROTOCOL_PASS = "PASS_SUPPLEMENTAL_AUTHORIZATION_PROTOCOL_EXECUTION_CLOSED"
AMENDMENT_PASS = "PASS_SUPPLEMENTAL_OWNER_EXECUTION_AUTHORIZATION"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_protocol() -> dict:
    value = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    errors: list[str] = []
    if value.get("status") != "FROZEN_AUTHORIZATION_INTAKE_PREPARED_EXECUTION_CLOSED":
        errors.append("Supplemental authorization protocol status changed")
    scope = value.get("scope", {})
    if scope.get("resource_ids") != ["PBC05", "PBC06", "PBC07", "PBC08"]:
        errors.append("Supplemental authorization scope changed")
    if scope.get("maximum_get_requests") != 4 or scope.get("maximum_attempts_per_resource") != 1:
        errors.append("Supplemental authorization request bound changed")
    release_path = ROOT / str(scope.get("release_path", ""))
    if not release_path.is_file() or sha256_file(release_path) != scope.get("release_sha256"):
        errors.append("Supplemental release binding changed")
    if verify_release().get("status") != RELEASE_PASS:
        errors.append("Supplemental release no longer verifies")
    for key in ("repeat_pbc01_through_pbc04_allowed", "raw_response_retention_allowed", "automatic_retry_allowed", "automatic_resume_allowed"):
        if scope.get(key) is not False:
            errors.append(f"Forbidden supplemental authorization behavior opened: {key}")
    authorization = value.get("required_owner_authorization", {})
    for key in ("must_be_explicit", "must_name_supplemental_network_execution", "must_authorize_pbc05_through_pbc08_scope"):
        if authorization.get(key) is not True:
            errors.append(f"Required owner authorization condition missing: {key}")
    if authorization.get("generic_continue_instruction_is_sufficient") is not False or authorization.get("received") is not False:
        errors.append("Generic continuation was promoted to supplemental network authorization")
    decision = value.get("decision", {})
    if decision.get("authorization_intake_prepared") is not True:
        errors.append("Supplemental authorization intake is not prepared")
    for key in ("owner_network_authorization_received", "network_execution_allowed_now", "commit_allowed", "push_allowed", "evidence_acceptance_allowed", "labeling_allowed", "training_allowed"):
        if decision.get(key) is not False:
            errors.append(f"Closed supplemental gate opened: {key}")
    return {"status": PROTOCOL_PASS if not errors else "FAIL", "errors": errors, "network_execution_allowed_now": False}


def verify_optional_amendment() -> dict:
    if not AMENDMENT.is_file() or not AMENDMENT_QA.is_file():
        return {"status": "ABSENT_AWAITING_EXPLICIT_OWNER_AUTHORIZATION", "valid": False, "errors": []}
    amendment = json.loads(AMENDMENT.read_text(encoding="utf-8"))
    qa = json.loads(AMENDMENT_QA.read_text(encoding="utf-8"))
    errors: list[str] = []
    if amendment.get("amendment_id") != "ISI_TARGET_TEXT_CORPUS_V1_PARSER_BOUND_CONTENT_SUPPLEMENTAL_EXECUTION_AMENDMENT_V1":
        errors.append("Supplemental execution amendment identity changed")
    if amendment.get("status") != "OWNER_AUTHORIZED_EXACT_PBC05_PBC08":
        errors.append("Supplemental execution amendment status changed")
    if amendment.get("protocol_sha256") != sha256_file(PROTOCOL):
        errors.append("Supplemental protocol hash mismatch")
    scope = json.loads(PROTOCOL.read_text(encoding="utf-8"))["scope"]
    release_path = ROOT / scope["release_path"]
    if amendment.get("release_sha256") != sha256_file(release_path):
        errors.append("Supplemental amendment release hash mismatch")
    if amendment.get("release_qa_sha256") != sha256_file(RELEASE_QA):
        errors.append("Supplemental amendment release-QA hash mismatch")
    authorization = amendment.get("owner_authorization_record", {})
    if authorization.get("received") is not True or authorization.get("scope") != "PBC05_PBC06_PBC07_PBC08_MAXIMUM_FOUR_GETS":
        errors.append("Supplemental owner authorization record invalid")
    text = str(authorization.get("text", ""))
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != authorization.get("text_sha256"):
        errors.append("Supplemental owner authorization text hash mismatch")
    if authorization.get("commit_authorized") is not True or authorization.get("push_authorized") is not True:
        errors.append("Supplemental commit/push authorization is absent")
    if authorization.get("repeat_pbc01_through_pbc04_authorized") is not False:
        errors.append("Supplemental authorization permits repeating PBC01-PBC04")
    binding = amendment.get("execution_binding", {})
    if binding.get("resource_ids") != ["PBC05", "PBC06", "PBC07", "PBC08"]:
        errors.append("Supplemental amendment resource binding changed")
    if binding.get("maximum_get_requests") != 4 or binding.get("maximum_attempts_per_resource") != 1:
        errors.append("Supplemental amendment request bound changed")
    for key in ("raw_response_retention_allowed", "automatic_retry_allowed", "automatic_resume_allowed"):
        if binding.get(key) is not False:
            errors.append(f"Supplemental amendment opened forbidden behavior: {key}")
    for key in ("continue_after_row_local_parser_failure", "stop_on_transport_or_provider_error", "no_overwrite"):
        if binding.get(key) is not True:
            errors.append(f"Supplemental amendment safeguard missing: {key}")
    if amendment.get("decision", {}).get("network_execution_allowed_after_committed_qa") is not True:
        errors.append("Supplemental amendment does not authorize the committed gate")
    for key in ("same_run_execution_before_push_allowed", "evidence_acceptance_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "model_operations_allowed", "training_allowed"):
        if amendment.get("decision", {}).get(key) is not False:
            errors.append(f"Supplemental amendment opened downstream gate: {key}")
    if qa.get("status") != AMENDMENT_PASS or qa.get("amendment_sha256") != sha256_file(AMENDMENT):
        errors.append("Supplemental amendment QA mismatch")
    qa_inputs = qa.get("inputs", {})
    if qa_inputs.get("protocol_sha256") != sha256_file(PROTOCOL):
        errors.append("Supplemental amendment QA protocol hash mismatch")
    if qa_inputs.get("release_sha256") != sha256_file(release_path):
        errors.append("Supplemental amendment QA release hash mismatch")
    if qa_inputs.get("release_qa_sha256") != sha256_file(RELEASE_QA):
        errors.append("Supplemental amendment QA release-QA hash mismatch")
    if qa.get("decision", {}).get("network_execution_allowed_in_current_uncommitted_state") is not False:
        errors.append("Supplemental amendment QA opened uncommitted execution")
    return {"status": AMENDMENT_PASS if not errors else "FAIL", "valid": not errors, "errors": errors}


if __name__ == "__main__":
    print(json.dumps({"protocol": verify_protocol(), "amendment": verify_optional_amendment()}, ensure_ascii=False, indent=2))
