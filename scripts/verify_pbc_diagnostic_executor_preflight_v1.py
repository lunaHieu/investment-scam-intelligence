"""Offline package preflight for a future, separately authorized PBC release.

This verifier has no network or execution path. A PASS means only that a
synthetic/candidate package is internally consistent; it never opens the
source-request gate.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_parser_bound_content_diagnostic_release_v1 import ROOT


PRIOR_RELEASE_ID = "ISI_TARGET_TEXT_CORPUS_V1_PARSER_BOUND_CONTENT_DIAGNOSTIC_RELEASE_V1"
PRIOR_RESULT_SHA256 = "5fcddbb84bb27867c139b972206e5483d78d8fefa91836cb5ffabf4f200fb07a"
EXPECTED_RESOURCE_IDS = ["PBC05", "PBC08"]
EXPECTED_RATIONALES = {
    "PBC05": "CHILD_FAILURE_DIAGNOSTIC_INCOMPLETE",
    "PBC08": "FORBIDDEN_KEY_DIAGNOSTIC_INCOMPLETE",
}
EXPECTED_URLS = {
    "PBC05": "https://aclanthology.org/2026.findings-emnlp.404.pdf",
    "PBC08": "https://huggingface.co/api/datasets/trannguyenthaituan/vietnamese_sms_dataset/commits/main",
}
FORBIDDEN_OUTPUTS = {
    "registry/analyses/target_text_corpus_v1_parser_bound_content_diagnostic_result_v1.json",
    "registry/analyses/target_text_corpus_v1_parser_bound_content_diagnostic_result_v1.json.partial",
    "registry/analyses/target_text_corpus_v1_parser_bound_content_diagnostic_result_v1.json.partial.tmp",
}
SAFE_PATH_PREFIX = "registry/analyses/"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json_sha256(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _parse_aware_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None


def _safe_relative_path(root: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    resolved_root = root.resolve()
    resolved = (resolved_root / candidate).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError:
        return None
    return resolved


def verify_candidate_bundle(
    release: Any,
    release_qa: Any,
    owner_authorization: Any,
    *,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Check a proposed release bundle without opening any execution gate."""

    errors: list[str] = []
    if not isinstance(release, dict):
        release = {}
        errors.append("CANDIDATE_RELEASE_NOT_OBJECT")
    if not isinstance(release_qa, dict):
        release_qa = {}
        errors.append("INDEPENDENT_QA_NOT_OBJECT")
    if not isinstance(owner_authorization, dict):
        owner_authorization = {}
        errors.append("OWNER_AUTHORIZATION_NOT_OBJECT")
    release_id = release.get("release_id")
    if not isinstance(release_id, str) or not release_id.endswith("_V2") or release_id == PRIOR_RELEASE_ID:
        errors.append("CANDIDATE_RELEASE_ID_NOT_NEW_V2")
    if release.get("status") != "FROZEN_PREPARATION_EXECUTION_CLOSED":
        errors.append("CANDIDATE_RELEASE_NOT_FROZEN_CLOSED")
    if release.get("prior_release_id") != PRIOR_RELEASE_ID:
        errors.append("PRIOR_RELEASE_ID_NOT_PINNED")
    if release.get("prior_result_sha256") != PRIOR_RESULT_SHA256:
        errors.append("PRIOR_RESULT_HASH_NOT_PINNED")
    created_at = _parse_aware_timestamp(release.get("created_at"))
    not_before = _parse_aware_timestamp(release.get("not_before"))
    if created_at is None or not_before is None:
        errors.append("RELEASE_TIMESTAMPS_MUST_BE_TIMEZONE_AWARE")
    elif not_before < created_at:
        errors.append("NOT_BEFORE_PRECEDES_RELEASE_CREATION")

    resources = release.get("resources")
    resources = resources if isinstance(resources, list) else []
    resource_ids = [item.get("resource_id") for item in resources if isinstance(item, dict)]
    if resource_ids != EXPECTED_RESOURCE_IDS:
        errors.append("RESOURCE_IDENTITY_OR_ORDER_CHANGED")
    for resource in resources:
        if not isinstance(resource, dict):
            errors.append("RESOURCE_ENTRY_NOT_OBJECT")
            continue
        expected_rationale = EXPECTED_RATIONALES.get(resource.get("resource_id"))
        if resource.get("technical_rationale_code") != expected_rationale:
            errors.append("TECHNICAL_RATIONALE_MISSING_OR_INVALID")
        if resource.get("url") != EXPECTED_URLS.get(resource.get("resource_id")):
            errors.append("RESOURCE_URL_NOT_PINNED_TO_APPROVED_ENDPOINT")

    expected_diagnostics = {
        "safe_contract_sha256": sha256_file(root / "scripts/pbc_safe_diagnostic_contract_v1.py"),
        "offline_harness_sha256": sha256_file(root / "scripts/pbc_offline_diagnostic_harness_v1.py"),
    }
    if release.get("diagnostic_tooling") != expected_diagnostics:
        errors.append("SAFE_DIAGNOSTIC_TOOLING_HASH_MISMATCH")

    contract = release.get("execution_contract")
    contract = contract if isinstance(contract, dict) else {}
    required_false = (
        "repeat_prior_release_allowed",
        "automatic_retry_allowed",
        "automatic_resume_allowed",
        "raw_response_retention_allowed",
        "dataset_file_download_allowed",
        "candidate_live_domain_access_allowed",
        "validation_or_test_open_allowed",
        "model_operations_allowed",
        "training_allowed",
    )
    for key in required_false:
        if contract.get(key) is not False:
            errors.append(f"EXECUTION_CONTRACT_NOT_CLOSED:{key}")
    if contract.get("no_overwrite") is not True:
        errors.append("NO_OVERWRITE_NOT_REQUIRED")
    for key in ("continue_after_row_local_parser_failure", "stop_on_transport_error", "stop_on_provider_http_error"):
        if contract.get(key) is not True:
            errors.append(f"FAIL_CLOSED_STOP_POLICY_MISSING:{key}")
    if contract.get("maximum_redirects") != 0:
        errors.append("REDIRECTS_MUST_BE_DISABLED")
    if contract.get("maximum_get_requests") != len(EXPECTED_RESOURCE_IDS):
        errors.append("REQUEST_BUDGET_MISMATCH")
    if contract.get("maximum_attempts_per_resource") != 1:
        errors.append("ATTEMPT_BUDGET_MISMATCH")
    if not isinstance(contract.get("minimum_request_interval_seconds"), (int, float)) or contract.get("minimum_request_interval_seconds", 0) < 60:
        errors.append("REQUEST_PACING_BELOW_MINIMUM")

    decision = release.get("decision")
    decision = decision if isinstance(decision, dict) else {}
    for key in (
        "network_execution_allowed_now", "evidence_acceptance_allowed",
        "dataset_acquisition_allowed", "labeling_allowed", "training_allowed",
    ):
        if decision.get(key) is not False:
            errors.append(f"RELEASE_DECISION_GATE_OPEN:{key}")

    release_hash = canonical_json_sha256(release)
    if release_qa.get("status") != "PASS_CANDIDATE_RELEASE_PREFLIGHT_ONLY":
        errors.append("INDEPENDENT_QA_STATUS_MISSING")
    if release_qa.get("release_canonical_sha256") != release_hash:
        errors.append("INDEPENDENT_QA_RELEASE_HASH_MISMATCH")
    if release_qa.get("independent_verifier_passed") is not True:
        errors.append("INDEPENDENT_VERIFIER_NOT_PASSED")
    qa_decision = release_qa.get("decision")
    qa_decision = qa_decision if isinstance(qa_decision, dict) else {}
    if qa_decision.get("network_execution_allowed_now") is not False:
        errors.append("INDEPENDENT_QA_OPENS_NETWORK_GATE")

    authorization = owner_authorization.get("authorization")
    authorization = authorization if isinstance(authorization, dict) else {}
    if authorization.get("received") is not True:
        errors.append("SEPARATE_OWNER_AUTHORIZATION_MISSING")
    if authorization.get("scope") != "EXECUTE_NEW_PBC_DIAGNOSTIC_RELEASE_V2":
        errors.append("OWNER_AUTHORIZATION_SCOPE_MISMATCH")
    if authorization.get("release_id") != release_id:
        errors.append("OWNER_AUTHORIZATION_RELEASE_ID_MISMATCH")
    if authorization.get("release_canonical_sha256") != release_hash:
        errors.append("OWNER_AUTHORIZATION_RELEASE_HASH_MISMATCH")
    if authorization.get("resource_ids") != EXPECTED_RESOURCE_IDS:
        errors.append("OWNER_AUTHORIZATION_RESOURCE_SCOPE_MISMATCH")
    if authorization.get("maximum_requests") != len(EXPECTED_RESOURCE_IDS):
        errors.append("OWNER_AUTHORIZATION_REQUEST_BUDGET_MISMATCH")
    if authorization.get("maximum_attempts_per_resource") != 1:
        errors.append("OWNER_AUTHORIZATION_ATTEMPT_BUDGET_MISMATCH")
    if authorization.get("repeat_prior_release_allowed") is not False:
        errors.append("OWNER_AUTHORIZATION_REOPENS_PRIOR_RELEASE")
    if authorization.get("retry_after_failure_allowed") is not False:
        errors.append("OWNER_AUTHORIZATION_ALLOWS_UNBOUNDED_RETRY")
    auth_constraints = owner_authorization.get("constraints")
    auth_constraints = auth_constraints if isinstance(auth_constraints, dict) else {}
    for key in (
        "candidate_live_domain_access_allowed", "dataset_file_download_allowed",
        "raw_response_retention_allowed", "validation_or_test_open_allowed",
        "labeling_allowed", "model_operations_allowed", "training_allowed",
    ):
        if auth_constraints.get(key) is not False:
            errors.append(f"OWNER_AUTHORIZATION_CONSTRAINT_NOT_CLOSED:{key}")

    output = release.get("planned_output")
    partial = release.get("planned_partial")
    temporary = f"{partial}.tmp" if isinstance(partial, str) else None
    planned_paths_new = True
    if not isinstance(output, str) or not output.startswith(SAFE_PATH_PREFIX):
        errors.append("PLANNED_OUTPUT_PATH_OUTSIDE_ANALYSIS_REGISTRY")
    if not isinstance(partial, str) or not partial.startswith(SAFE_PATH_PREFIX):
        errors.append("PLANNED_PARTIAL_PATH_OUTSIDE_ANALYSIS_REGISTRY")
    if (
        (isinstance(output, str) and output in (partial, temporary))
        or (isinstance(partial, str) and partial == temporary)
        or (isinstance(output, str) and output in FORBIDDEN_OUTPUTS)
        or (isinstance(partial, str) and partial in FORBIDDEN_OUTPUTS)
        or (isinstance(temporary, str) and temporary in FORBIDDEN_OUTPUTS)
    ):
        errors.append("PLANNED_OUTPUT_REUSES_IMMUTABLE_PATH")
        planned_paths_new = False
    for relative in (output, partial, temporary):
        path = _safe_relative_path(root, relative)
        if path is None:
            errors.append("PLANNED_PATH_INVALID_OR_ESCAPES_ROOT")
            planned_paths_new = False
        elif path.exists():
            errors.append("PLANNED_OUTPUT_ALREADY_EXISTS")
            planned_paths_new = False

    passed = not errors
    return {
        "verification_id": "ISI_PBC_DIAGNOSTIC_EXECUTOR_CANDIDATE_PREFLIGHT_V1",
        "status": "PASS_CANDIDATE_PREFLIGHT_EXECUTION_STILL_CLOSED" if passed else "FAIL_CANDIDATE_PREFLIGHT",
        "release_id": release_id,
        "release_canonical_sha256": release_hash,
        "checks": {
            "ordered_resource_ids": resource_ids,
            "diagnostic_tooling_hashes_pinned": release.get("diagnostic_tooling") == expected_diagnostics,
            "independent_qa_bound_to_release": release_qa.get("release_canonical_sha256") == release_hash,
            "separate_owner_authorization_bound": authorization.get("release_canonical_sha256") == release_hash,
            "planned_output_paths_are_new": planned_paths_new,
        },
        "decision": {
            "candidate_package_consistent": passed,
            "network_execution_allowed": False,
            "separate_execution_gate_still_required": True,
            "same_release_retry_allowed": False,
            "training_allowed": False,
        },
        "errors": errors,
        "safety_contract": {
            "network_operations": 0,
            "candidate_domain_access_operations": 0,
            "raw_responses_retained": 0,
            "labels_created": 0,
            "validation_or_test_rows_opened": 0,
            "model_operations": 0,
        },
    }
