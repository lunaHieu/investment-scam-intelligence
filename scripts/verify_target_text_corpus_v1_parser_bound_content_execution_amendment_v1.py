"""Independently verify the exact-eight parser-bound execution amendment."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from scripts.verify_target_text_corpus_v1_parser_bound_content_execution_authorization_protocol_v1 import (
    PASS_STATUS as PROTOCOL_PASS,
    verify as verify_protocol,
)


ROOT = Path(__file__).resolve().parents[1]
AMENDMENT = ROOT / "configs" / "target_text_corpus_v1_parser_bound_content_execution_amendment_v1.json"
QA = ROOT / "registry" / "analyses" / "target_text_corpus_v1_parser_bound_content_execution_amendment_qa_v1.json"
PASS_STATUS = "PASS_EXACT_EIGHT_OWNER_AUTHORIZED_AMENDMENT"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tracked(path: Path) -> bool:
    relative = str(path.relative_to(ROOT)).replace("\\", "/")
    return subprocess.run(
        ["git", "ls-files", "--error-unmatch", relative], cwd=ROOT, capture_output=True
    ).returncode == 0


def verify_registered_qa() -> dict:
    errors: list[str] = []
    if not QA.is_file():
        return {"valid": False, "errors": ["Independent QA is absent"]}
    value = json.loads(QA.read_text(encoding="utf-8"))
    if value.get("verification_id") != "ISI_TARGET_TEXT_CORPUS_V1_PARSER_BOUND_CONTENT_EXECUTION_AMENDMENT_QA_V1":
        errors.append("Independent QA identity changed")
    if value.get("status") != PASS_STATUS:
        errors.append("Independent QA status changed")
    if value.get("amendment", {}).get("sha256") != sha256_file(AMENDMENT):
        errors.append("Independent QA amendment hash mismatch")
    for section in ("inputs", "implementation"):
        for item in value.get(section, []):
            target = ROOT / str(item.get("path", ""))
            if not target.is_file() or sha256_file(target) != item.get("sha256"):
                errors.append(f"Independent QA hash mismatch: {item.get('path')}")
    decision = value.get("decision", {})
    if decision.get("network_execution_allowed_in_current_uncommitted_state") is not False:
        errors.append("Independent QA opened uncommitted execution")
    if decision.get("execution_allowed_only_after_amendment_and_qa_are_committed_and_pushed") is not True:
        errors.append("Independent QA lost the committed-and-pushed gate")
    for key in ("commit_allowed_by_this_qa", "push_allowed_by_this_qa", "training_allowed"):
        if decision.get(key) is not False:
            errors.append(f"Independent QA expanded authority: {key}")
    return {"valid": not errors, "errors": errors}


def verify(path: Path = AMENDMENT) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if value.get("amendment_id") != "ISI_TARGET_TEXT_CORPUS_V1_PARSER_BOUND_CONTENT_EXECUTION_AMENDMENT_V1":
        errors.append("Amendment identity changed")
    if value.get("status") != "OWNER_AUTHORIZED_PENDING_COMMITTED_QA":
        errors.append("Amendment status changed")
    protocol_check = verify_protocol()
    if protocol_check.get("status") != PROTOCOL_PASS:
        errors.append("Authorization protocol no longer verifies")

    inputs = {item["role"]: item for item in value.get("inputs", [])}
    if set(inputs) != {"authorization_protocol", "parser_bound_release", "release_qa"}:
        errors.append("Amendment inputs changed")
    for role, item in inputs.items():
        target = ROOT / str(item.get("path", ""))
        if not target.is_file() or sha256_file(target) != item.get("sha256"):
            errors.append(f"Pinned input mismatch: {role}")

    release_path = ROOT / str(inputs.get("parser_bound_release", {}).get("path", ""))
    release = json.loads(release_path.read_text(encoding="utf-8")) if release_path.is_file() else {}
    binding = value.get("execution_binding", {})
    expected_ids = [f"PBC{number:02}" for number in range(1, 9)]
    resources = release.get("resources", [])
    if binding.get("resource_ids") != expected_ids or [item.get("resource_id") for item in resources] != expected_ids:
        errors.append("Exact resource population changed")
    if binding.get("exact_get_requests") != 8 or binding.get("maximum_attempts_per_resource") != 1:
        errors.append("Request or attempt bound changed")
    if binding.get("maximum_total_response_bytes") != 3148024:
        errors.append("Response-byte bound changed")
    if binding.get("authorized_executor_module") != "scripts.orchestrate_target_text_corpus_v1_parser_bound_content_v2":
        errors.append("Authorized executor changed")
    for key in (
        "automatic_retry_allowed", "automatic_resume_allowed", "raw_response_retention_allowed",
        "candidate_live_domain_access_allowed", "dataset_file_download_allowed",
    ):
        if binding.get(key) is not False:
            errors.append(f"Forbidden execution behavior opened: {key}")
    for key in ("stop_after_first_failure", "no_overwrite", "pdf_visual_review_required_before_evidence_acceptance"):
        if binding.get(key) is not True:
            errors.append(f"Required safeguard missing: {key}")

    authorization = value.get("owner_authorization_record", {})
    if authorization.get("received") is not True:
        errors.append("Owner network authorization is absent")
    if authorization.get("user_response") != "được cho phép":
        errors.append("Owner response changed")
    if hashlib.sha256(str(authorization.get("user_response", "")).encode("utf-8")).hexdigest() != authorization.get("user_response_sha256"):
        errors.append("Owner response hash mismatch")
    if authorization.get("commit_authorized") is not False or authorization.get("push_authorized") is not False:
        errors.append("Network authorization was incorrectly expanded to Git authorization")

    decision = value.get("decision", {})
    if decision.get("owner_network_authorization_received") is not True or decision.get("execution_scope_authorized") is not True:
        errors.append("Owner-authorized scope is not recorded")
    if decision.get("network_execution_allowed_before_committed_qa") is not False:
        errors.append("Network gate opened before committed QA")
    for key in (
        "commit_allowed_by_this_amendment", "push_allowed_by_this_amendment",
        "evidence_acceptance_allowed", "labeling_allowed", "validation_or_test_opening_allowed",
        "model_operations_allowed", "training_allowed",
    ):
        if decision.get(key) is not False:
            errors.append(f"Forbidden downstream gate opened: {key}")

    output = ROOT / str(release.get("planned_output", ""))
    partial = ROOT / str(release.get("planned_partial", ""))
    outputs_absent = not output.exists() and not partial.exists() and not Path(str(partial) + ".tmp").exists()
    if not outputs_absent:
        errors.append("Planned final, partial, or checkpoint output already exists")

    return {
        "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_PARSER_BOUND_CONTENT_EXECUTION_AMENDMENT_QA_V1",
        "status": PASS_STATUS if not errors else "FAIL",
        "amendment": {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256_file(path)},
        "checks": {
            "resource_count": len(resources),
            "resource_ids": [item.get("resource_id") for item in resources],
            "authorities": sorted({urlparse(str(item.get("url", ""))).hostname for item in resources}),
            "owner_network_authorization_received": authorization.get("received"),
            "commit_authorized": authorization.get("commit_authorized"),
            "push_authorized": authorization.get("push_authorized"),
            "amendment_tracked": tracked(path),
            "independent_qa_tracked": QA.is_file() and tracked(QA),
            "planned_outputs_absent": outputs_absent,
        },
        "decision": {
            "amendment_verified": not errors,
            "network_execution_allowed_now": False,
            "commit_allowed": False,
            "push_allowed": False,
            "training_allowed": False,
        },
        "errors": errors,
        "safety_contract": {"network_operations": 0, "labels_created": 0, "model_operations": 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--amendment", type=Path, default=AMENDMENT)
    args = parser.parse_args()
    result = verify(args.amendment)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
