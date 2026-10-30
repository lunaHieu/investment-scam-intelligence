"""Verify the parser-bound execution-authorization intake without network access."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "configs" / "target_text_corpus_v1_parser_bound_content_execution_authorization_protocol_v1.json"
PASS_STATUS = "PASS_AUTHORIZATION_INTAKE_PREPARED_EXECUTION_CLOSED"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout.strip()


def verify(path: Path = PROTOCOL) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if value.get("protocol_id") != "ISI_TARGET_TEXT_CORPUS_V1_PARSER_BOUND_CONTENT_EXECUTION_AUTHORIZATION_PROTOCOL_V1":
        errors.append("Protocol identity changed")
    if value.get("status") != "FROZEN_AUTHORIZATION_INTAKE_PREPARED_EXECUTION_CLOSED":
        errors.append("Protocol status changed")

    inputs = {item["role"]: item for item in value.get("inputs", [])}
    if set(inputs) != {"implementation_commit", "parser_bound_release", "local_release_qa", "execution_readiness_audit"}:
        errors.append("Protocol input roles changed")
    commit = inputs.get("implementation_commit", {}).get("commit")
    if commit != "e80b2027bc6e322e7665e04913d0a8169260a8d9":
        errors.append("Implementation commit binding changed")
    elif subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=ROOT).returncode != 0:
        errors.append("Implementation commit is not an ancestor of HEAD")

    for role in ("parser_bound_release", "local_release_qa", "execution_readiness_audit"):
        item = inputs.get(role, {})
        target = ROOT / str(item.get("path", ""))
        if not target.is_file() or sha256_file(target) != item.get("sha256"):
            errors.append(f"Pinned input mismatch: {role}")

    release_path = ROOT / str(inputs.get("parser_bound_release", {}).get("path", ""))
    release = json.loads(release_path.read_text(encoding="utf-8")) if release_path.is_file() else {}
    scope = value.get("authorization_scope", {})
    expected_ids = [f"PBC{number:02}" for number in range(1, 9)]
    resources = release.get("resources", [])
    if scope.get("resource_ids") != expected_ids or [item.get("resource_id") for item in resources] != expected_ids:
        errors.append("Exact eight-resource identity binding changed")
    if scope.get("exact_get_requests") != 8 or release.get("execution_contract", {}).get("exact_get_requests") != 8:
        errors.append("Exact request bound changed")
    if scope.get("maximum_total_response_bytes") != 3148024:
        errors.append("Total response-byte bound changed")
    authorities = sorted({urlparse(str(item.get("url", ""))).hostname for item in resources})
    if authorities != scope.get("allowed_authorities"):
        errors.append("Authority binding changed")
    for key in (
        "raw_response_retention_allowed", "dataset_file_download_allowed",
        "candidate_live_domain_access_allowed", "repository_clone_allowed",
        "automatic_retry_allowed", "automatic_resume_allowed",
    ):
        if scope.get(key) is not False:
            errors.append(f"Forbidden scope opened: {key}")
    for key in ("stop_after_first_failure", "no_overwrite", "pdf_visual_review_required_before_evidence_acceptance"):
        if scope.get(key) is not True:
            errors.append(f"Required safeguard missing: {key}")

    authorization = value.get("required_owner_authorization", {})
    for key in ("must_be_explicit", "must_name_network_execution", "must_authorize_exact_eight_resource_scope"):
        if authorization.get(key) is not True:
            errors.append(f"Owner-authorization requirement missing: {key}")
    if authorization.get("generic_continue_instruction_is_sufficient") is not False:
        errors.append("Generic continuation instruction was treated as network authorization")
    if authorization.get("received") is not False or authorization.get("received_at") is not None or authorization.get("authorization_text_sha256") is not None:
        errors.append("Owner network authorization was recorded prematurely")

    decision = value.get("decision", {})
    if decision.get("authorization_intake_prepared") is not True:
        errors.append("Authorization intake is not prepared")
    for key in (
        "owner_network_authorization_received", "execution_amendment_may_be_created_now",
        "network_execution_allowed_now", "dataset_acquisition_allowed",
        "evidence_acceptance_allowed", "labeling_allowed",
        "validation_or_test_opening_allowed", "model_operations_allowed", "training_allowed",
    ):
        if decision.get(key) is not False:
            errors.append(f"Closed decision gate opened: {key}")

    planned = [ROOT / str(release.get("planned_output", "")), ROOT / str(release.get("planned_partial", ""))]
    planned.append(Path(str(planned[-1]) + ".tmp"))
    if any(item.exists() for item in planned):
        errors.append("A planned final, partial, or checkpoint output already exists")

    return {
        "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_PARSER_BOUND_CONTENT_EXECUTION_AUTHORIZATION_PROTOCOL_QA_V1",
        "status": PASS_STATUS if not errors else "FAIL",
        "protocol": {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256_file(path)},
        "checks": {
            "implementation_commit": commit,
            "head": git("rev-parse", "HEAD"),
            "resource_count": len(resources),
            "resource_ids": [item.get("resource_id") for item in resources],
            "authorities": authorities,
            "planned_outputs_absent": not any(item.exists() for item in planned),
            "owner_network_authorization_received": authorization.get("received"),
        },
        "decision": {
            "authorization_intake_prepared": not errors,
            "execution_amendment_may_be_created_now": False,
            "network_execution_allowed_now": False,
            "training_allowed": False,
        },
        "errors": errors,
        "safety_contract": {"network_operations": 0, "labels_created": 0, "model_operations": 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    args = parser.parse_args()
    result = verify(args.protocol)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
