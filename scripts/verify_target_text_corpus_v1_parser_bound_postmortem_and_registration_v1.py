"""Verify offline PBC05/PBC08 postmortem and exact PBC06/PBC07 registration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.verify_target_text_corpus_v1_parser_bound_content_release_v1 import ROOT
from scripts.verify_target_text_corpus_v1_parser_bound_content_supplemental_result_v1 import (
    PASS_STATUS as RESULT_PASS,
    verify_result,
)


RESULT = ROOT / "registry" / "analyses" / "target_text_corpus_v1_parser_bound_content_supplemental_result_v1.json"
POSTMORTEM = ROOT / "registry" / "analyses" / "target_text_corpus_v1_pbc05_pbc08_offline_postmortem_v1.json"
REGISTRATION = ROOT / "registry" / "analyses" / "target_text_corpus_v1_pbc06_pbc07_success_registration_v1.json"
QA = ROOT / "registry" / "analyses" / "target_text_corpus_v1_parser_bound_postmortem_and_registration_qa_v1.json"
PASS_STATUS = "PASS_OFFLINE_POSTMORTEM_AND_EXACT_TWO_SUCCESS_REGISTRATION"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify() -> dict:
    errors: list[str] = []
    qa = json.loads(QA.read_text(encoding="utf-8"))
    pinned = {
        item["role"]: item
        for item in qa.get("inputs", []) + qa.get("implementation", [])
    }
    expected_pins = {
        "supplemental_result": RESULT,
        "bounded_postmortem": POSTMORTEM,
        "success_registration": REGISTRATION,
        "independent_verifier": Path(__file__),
        "tests": ROOT / "tests" / "test_target_text_corpus_v1_parser_bound_postmortem_and_registration_v1.py",
        "documentation": ROOT / "docs" / "target-text-corpus-v1-pbc05-pbc08-offline-postmortem-and-pbc06-pbc07-registration-v1.md",
    }
    if set(pinned) != set(expected_pins):
        errors.append("Persistent QA hash graph roles changed")
    for role, source in expected_pins.items():
        if not source.is_file() or pinned.get(role, {}).get("sha256") != sha256_file(source):
            errors.append(f"Persistent QA hash mismatch: {role}")
    if verify_result(RESULT).get("status") != RESULT_PASS:
        errors.append("Supplemental result no longer verifies")
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    rows = {row["resource_id"]: row for row in result["resources"]}
    result_hash = sha256_file(RESULT)

    postmortem = json.loads(POSTMORTEM.read_text(encoding="utf-8"))
    if postmortem.get("status") != "PASS_BOUNDED_OFFLINE_POSTMORTEM_EXACT_CAUSES_NOT_OVERCLAIMED":
        errors.append("Offline postmortem status changed")
    if postmortem["inputs"][0].get("sha256") != result_hash:
        errors.append("Postmortem result hash mismatch")
    pbc05 = rows["PBC05"]
    confirmed05 = postmortem["pbc05"]["confirmed"]
    if confirmed05.get("failure_stage") != pbc05["diagnostic_details"]["stage"]:
        errors.append("PBC05 failure stage mismatch")
    if confirmed05.get("subprocess_returncode") != pbc05["diagnostic_details"]["returncode"]:
        errors.append("PBC05 return code mismatch")
    diagnostic_mapping = {
        "stdout_bytes": "stdout_bytes",
        "stdout_sha256": "stdout_sha256",
        "stderr_bytes": "stderr_bytes",
        "stderr_sha256": "stderr_sha256",
    }
    for postmortem_key, result_key in diagnostic_mapping.items():
        if confirmed05.get(postmortem_key) != pbc05["diagnostic_details"].get(result_key):
            errors.append(f"PBC05 diagnostic mismatch: {postmortem_key}")
    for key in ("http_status", "content_type", "response_bytes", "response_sha256"):
        if confirmed05.get(key) != pbc05.get(key):
            errors.append(f"PBC05 response identity mismatch: {key}")
    if postmortem["pbc05"].get("exact_exception_recoverable_offline") is not False:
        errors.append("PBC05 exact exception was overclaimed")
    pbc08 = rows["PBC08"]
    confirmed08 = postmortem["pbc08"]["confirmed"]
    if confirmed08.get("diagnostic_code") != pbc08["diagnostic_code"]:
        errors.append("PBC08 diagnostic mismatch")
    for key in ("http_status", "content_type", "response_bytes", "response_sha256"):
        if confirmed08.get(key) != pbc08.get(key):
            errors.append(f"PBC08 response identity mismatch: {key}")
    if postmortem["pbc08"].get("exact_value_error_recoverable_offline") is not False:
        errors.append("PBC08 exact ValueError was overclaimed")
    for branch in (postmortem["pbc05"], postmortem["pbc08"]):
        if any(item.get("status") not in {"PLAUSIBLE_NOT_CONFIRMED", "LOWER_PROBABILITY_NOT_EXCLUDED"} for item in branch["bounded_hypotheses"]):
            errors.append("A postmortem hypothesis was promoted to fact")

    registration = json.loads(REGISTRATION.read_text(encoding="utf-8"))
    if registration.get("status") != "PASS_TWO_METADATA_DOCUMENTATION_ARTIFACTS_REGISTERED_NO_DATA_ADMISSION":
        errors.append("Success registration status changed")
    if registration["inputs"][0].get("sha256") != result_hash:
        errors.append("Registration result hash mismatch")
    items = registration.get("registrations", [])
    if [item.get("resource_id") for item in items] != ["PBC06", "PBC07"]:
        errors.append("Success registration population changed")
    for item in items:
        row = rows[item["resource_id"]]
        if row["outcome"] != "SUCCESS" or item.get("response_sha256") != row["response_sha256"] or item.get("response_bytes") != row["response_bytes"]:
            errors.append(f"Registered success identity mismatch: {item.get('resource_id')}")
    pbc06 = items[0]
    output06 = rows["PBC06"]["structured_output"]
    if pbc06.get("revision_sha") != output06["sha"] or pbc06.get("sibling_paths") != output06["sibling_paths"] or pbc06.get("registered_tags") != output06["tags"]:
        errors.append("PBC06 structured metadata mismatch")
    pbc07 = items[1]
    if pbc07.get("retained_section_names") != list(rows["PBC07"]["structured_output"]["sections"]):
        errors.append("PBC07 retained section registration mismatch")
    decision = registration.get("decision", {})
    if decision.get("metadata_registration_complete") is not True:
        errors.append("Metadata registration not complete")
    for key in ("dataset_download_allowed", "validation_or_test_opening_allowed", "model_operations_allowed", "training_allowed"):
        if decision.get(key) is not False:
            errors.append(f"Registration opened forbidden gate: {key}")
    if decision.get("dataset_rows_admitted") != 0 or decision.get("labels_created") != 0:
        errors.append("Registration admitted rows or labels")

    return {
        "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_PARSER_BOUND_POSTMORTEM_AND_REGISTRATION_QA_V1",
        "status": PASS_STATUS if not errors else "FAIL",
        "checks": {
            "postmortem_resources": ["PBC05", "PBC08"],
            "registered_success_resources": [item.get("resource_id") for item in items],
            "pbc05_confirmed_stage": confirmed05.get("failure_stage"),
            "pbc08_exact_reason_recoverable": postmortem["pbc08"].get("exact_value_error_recoverable_offline"),
            "dataset_rows_admitted": decision.get("dataset_rows_admitted"),
            "labels_created": decision.get("labels_created"),
        },
        "decision": {"offline_review_complete": not errors, "network_execution_allowed": False, "training_allowed": False},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "labels_created": 0, "model_operations": 0},
    }


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
