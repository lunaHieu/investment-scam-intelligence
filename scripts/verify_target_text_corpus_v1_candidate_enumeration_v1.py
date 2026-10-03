"""Verify the frozen Target Text Corpus V1 production candidate enumeration."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


ANALYSIS_ID = "ISI_TARGET_TEXT_CORPUS_V1_CANDIDATE_ENUMERATION_V1"
EXPECTED_STATUS = "FROZEN_BALANCED_PROVENANCE_QUEUE_QA_PASS_CAPTURE_BLOCKED"
EXPECTED_CHANNEL_COUNTS = {
    "CONFIRMED_REGULATOR_LINKED_WEBSITE": 10,
    "CONFIRMED_CFTC_RED_LINKED_WAYBACK_WEBSITE": 10,
    "LEGITIMATE_REGISTER_LINKED_WEBSITE": 10,
    "LEGITIMATE_SEC_EDGAR_LINKED_WAYBACK_WEBSITE": 10,
}
EXPECTED_SAFETY = {
    "network_operations": 0,
    "historical_authorized_reference_network_operations_registered": 39,
    "domain_access_allowed": False,
    "candidate_domain_access_operations": 0,
    "candidate_artifact_captures": 0,
    "labels_created": 0,
    "labels_changed": 0,
    "model_fit_operations": 0,
    "model_scoring_operations": 0,
    "validation_or_test_openings": 0,
    "training_allowed": False,
    "deployment_allowed": False,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"Expected JSON object at {path}:{line_number}")
        rows.append(value)
    return rows


def resolve(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def verify_registry(registry_path: Path) -> dict[str, Any]:
    registry = load_json(registry_path)
    root = registry_path.resolve().parents[2]
    errors: list[str] = []
    checked: list[dict[str, object]] = []
    role_paths: dict[str, Path] = {}

    if registry.get("analysis_id") != ANALYSIS_ID:
        errors.append("Unexpected analysis ID")
    if registry.get("status") != EXPECTED_STATUS:
        errors.append("Unexpected registry status")

    items = (
        list(registry.get("inputs", []))
        + list(registry.get("implementation", []))
        + list(registry.get("outputs", []))
    )
    for item in items:
        role = str(item.get("role"))
        path = resolve(root, item.get("path", ""))
        actual = sha256_file(path) if path.is_file() else None
        if role in role_paths:
            errors.append(f"Duplicate artifact role: {role}")
        role_paths[role] = path
        checked.append({"role": role, "path": str(path), "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"Artifact missing or changed: {role}")
        if role in {"private_sec_identity_artifact", "sec_edgar_user_agent_identity"} or (
            "\\private\\" in str(path).lower()
        ):
            errors.append(f"Private SEC identity must not be registered: {role}")

    required_roles = {
        "ready_prerequisite_ledger",
        "reference_acquisition_inventory",
        "opened_external_exclusion_index",
        "confirmed_regulator_disjoint_pool",
        "confirmed_cftc_pool",
        "legitimate_iapd_disjoint_pool",
        "legitimate_edgar_pool",
        "sec_edgar_independent_provenance_review",
        "candidate_queue",
        "enumeration_report",
        "independent_provenance_qa",
    }
    missing = sorted(required_roles - role_paths.keys())
    if missing:
        errors.append(f"Registry lacks required artifact roles: {missing}")

    queue: list[dict[str, Any]] = []
    if "candidate_queue" in role_paths and role_paths["candidate_queue"].is_file():
        queue = load_jsonl(role_paths["candidate_queue"])
        counts = Counter(str(row.get("channel_id")) for row in queue)
        if len(queue) != 40:
            errors.append("Candidate queue must contain exactly 40 rows")
        if dict(counts) != EXPECTED_CHANNEL_COUNTS:
            errors.append(f"Candidate channel counts changed: {dict(counts)}")
        ids = [str(row.get("candidate_id")) for row in queue]
        hosts = [str(row.get("candidate_identity", {}).get("normalized_host")) for row in queue]
        if len(ids) != len(set(ids)):
            errors.append("Candidate IDs are not unique")
        if len(hosts) != len(set(hosts)):
            errors.append("Candidate hosts are not unique")
        for row in queue:
            review = row.get("review_state", {})
            if review.get("ground_truth_status") != "UNCERTAIN":
                errors.append("Candidate ground-truth status changed before review")
                break
            if review.get("training_eligible") != "NO":
                errors.append("Candidate became training-eligible before adjudication")
                break
            if review.get("label_created") is not False:
                errors.append("Candidate label was created before adjudication")
                break

    if "independent_provenance_qa" in role_paths and role_paths[
        "independent_provenance_qa"
    ].is_file():
        qa = load_json(role_paths["independent_provenance_qa"])
        if qa.get("status") != "PASS_PROVENANCE_QUEUE_FROZEN_CAPTURE_BLOCKED":
            errors.append("Independent provenance QA did not pass")
        checks = qa.get("checks", {})
        required_checks = {
            "candidate_schema_valid": True,
            "unique_candidate_ids": True,
            "unique_candidate_hosts": True,
            "opened_host_overlap_count": 0,
            "deterministic_selection_independently_reproduced": True,
            "reference_artifact_hashes_verified": True,
            "channel_counts": EXPECTED_CHANNEL_COUNTS,
        }
        if checks != required_checks:
            errors.append("Independent provenance QA checks changed")
        if queue and qa.get("queue", {}).get("sha256") != sha256_file(
            role_paths["candidate_queue"]
        ):
            errors.append("Independent QA queue hash does not match")

    if "reference_acquisition_inventory" in role_paths and role_paths[
        "reference_acquisition_inventory"
    ].is_file():
        inventory = load_json(role_paths["reference_acquisition_inventory"])
        if inventory.get("safety_contract", {}).get("candidate_domain_access_operations") != 0:
            errors.append("Reference acquisition inventory reports candidate-domain access")
        source_counts = {
            "CFTC_RED": inventory.get("cftc", {}).get("network_request_count"),
            "SEC_EDGAR": inventory.get("sec", {}).get("network_request_count"),
        }
        if source_counts != {"CFTC_RED": 17, "SEC_EDGAR": 22}:
            errors.append(f"Reference acquisition request counts changed: {source_counts}")

    if "ready_prerequisite_ledger" in role_paths and role_paths[
        "ready_prerequisite_ledger"
    ].is_file():
        ledger = load_json(role_paths["ready_prerequisite_ledger"])
        if ledger.get("status") != "READY_FOR_BALANCED_ENUMERATION":
            errors.append("Prerequisite ledger is not ready for offline enumeration")
        release = ledger.get("release_gate", {})
        if release.get("candidate_enumeration_allowed") is not True:
            errors.append("Prerequisite ledger did not release candidate enumeration")
        if release.get("network_execution_allowed") is not False:
            errors.append("Prerequisite ledger unexpectedly released network execution")

    if registry.get("safety_contract") != EXPECTED_SAFETY:
        errors.append("Registry safety contract changed")
    decision = registry.get("decision", {})
    if decision.get("candidate_capture_allowed") is not False:
        errors.append("Candidate capture must remain blocked at this milestone")
    if decision.get("binary_labeling_allowed") is not False:
        errors.append("Binary labeling must remain blocked at this milestone")

    return {
        "analysis_id": registry.get("analysis_id"),
        "valid": not errors,
        "status": registry.get("status"),
        "checked_artifact_count": len(checked),
        "candidate_count": len(queue),
        "channel_counts": dict(Counter(str(row.get("channel_id")) for row in queue)),
        "candidate_capture_allowed": False,
        "binary_labeling_allowed": False,
        "errors": errors,
        "checked": checked,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    args = parser.parse_args()
    result = verify_registry(args.registry)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
