"""Verify the PBC05/PBC08 cross-version offline closeout without network I/O."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry/analyses/pbc05_pbc08_offline_closeout_v2.json"
QA_OUTPUT = ROOT / "registry/analyses/pbc05_pbc08_offline_closeout_v2_qa.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def verify(registry_path: Path = REGISTRY) -> dict[str, Any]:
    registry = load_json(registry_path)
    errors: list[str] = []
    checked_inputs: list[dict[str, str]] = []
    documents: list[dict[str, str]] = []

    for item in registry.get("inputs", []):
        path = ROOT / item["path"]
        if not path.is_file():
            errors.append(f"missing pinned input: {item['role']}")
            continue
        actual = sha256_file(path)
        checked_inputs.append({"role": item["role"], "path": item["path"], "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"pinned input hash mismatch: {item['role']}")
    for item in registry.get("implementation", []):
        path = ROOT / item["path"]
        if not path.is_file():
            errors.append(f"missing documentation: {item['role']}")
            continue
        actual = sha256_file(path)
        documents.append({"role": item["role"], "path": item["path"], "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"documentation hash mismatch: {item['role']}")

    by_role = {item["role"]: ROOT / item["path"] for item in registry.get("inputs", [])}
    earlier = load_json(by_role["earlier_parser_bound_result"])
    supplemental = load_json(by_role["supplemental_result"])
    latest = load_json(by_role["latest_diagnostic_result"])
    latest_qa = load_json(by_role["latest_independent_result_qa"])
    preflight = load_json(by_role["current_candidate_preflight"])

    def resource(result: dict[str, Any], resource_id: str) -> dict[str, Any]:
        return next(row for row in result.get("resources", []) if row.get("resource_id") == resource_id)

    old05 = resource(earlier, "PBC05")
    old08 = resource(earlier, "PBC08")
    sup05 = resource(supplemental, "PBC05")
    sup08 = resource(supplemental, "PBC08")
    new05 = resource(latest, "PBC05")
    new08 = resource(latest, "PBC08")
    sup06 = resource(supplemental, "PBC06")
    sup07 = resource(supplemental, "PBC07")
    qa05 = next(row for row in latest_qa.get("row_findings", []) if row.get("resource_id") == "PBC05")
    qa08 = next(row for row in latest_qa.get("row_findings", []) if row.get("resource_id") == "PBC08")

    pbc05_state = registry.get("attempt_history", {}).get("PBC05", {})
    pbc08_state = registry.get("attempt_history", {}).get("PBC08", {})
    checks = {
        "earlier_pbc05_parser_failure_present": old05.get("outcome") == "PARSER_REJECTED",
        "earlier_pbc08_was_skipped_not_requested": (
            old08.get("outcome") == "SKIPPED_AFTER_FAILURE"
            and old08.get("diagnostic_code") == "EARLIER_RESOURCE_FAILED"
            and old08.get("http_status") is None
            and old08.get("response_bytes") == 0
        ),
        "supplemental_pbc05_section_error_759_bytes": (
            sup05.get("diagnostic_details", {}).get("stage") == "SECTION_EXTRACTION"
            and sup05.get("diagnostic_details", {}).get("returncode") == 1
            and sup05.get("diagnostic_details", {}).get("stderr_bytes") == 759
        ),
        "latest_pbc05_section_error_710_bytes": (
            new05.get("diagnostic_details", {}).get("stage") == "SECTION_EXTRACTION"
            and new05.get("diagnostic_details", {}).get("returncode") == 1
            and new05.get("diagnostic_details", {}).get("stderr_bytes") == 710
        ),
        "pbc05_instrumented_response_hash_same": (
            sup05.get("response_sha256") == new05.get("response_sha256")
            == pbc05_state.get("response_sha256_on_instrumented_runs")
        ),
        "pbc05_instrumented_stderr_hashes_differ": (
            sup05.get("diagnostic_details", {}).get("stderr_sha256")
            != new05.get("diagnostic_details", {}).get("stderr_sha256")
        ),
        "pbc08_only_two_actual_attempts": (
            pbc08_state.get("actual_attempts") == 2
            and pbc08_state.get("skipped_in_earlier_artifact") is True
            and sup08.get("outcome") == "PARSER_REJECTED"
            and new08.get("outcome") == "PARSER_REJECTED"
        ),
        "pbc08_latest_guard_confirmed_key_not_retained": (
            new08.get("diagnostic_code") == "PARSER_REJECTED_FORBIDDEN_DATASET_KEY_PRESENT"
            and qa08.get("exact_forbidden_key_retained") is False
        ),
        "latest_result_independent_qa_passed": latest_qa.get("status") == "PASS_EXACT_TWO_ROW_DIAGNOSTIC_RESULT_VERIFIED",
        "pbc06_and_pbc07_provenance_only_successes": sup06.get("outcome") == "SUCCESS" and sup07.get("outcome") == "SUCCESS",
        "raw_responses_not_retained": all(
            row.get("raw_response_retained") is False for row in (sup05, sup08, new05, new08)
        ),
        "candidate_preflight_did_not_open_execution": (
            preflight.get("decision", {}).get("network_execution_allowed") is False
            and preflight.get("decision", {}).get("actual_release_created") is False
        ),
        "malware_scan_not_claimed": registry.get("data_use_state", {}).get("malware_scan_recorded") is False,
        "no_data_rows_or_labels": (
            registry.get("data_use_state", {}).get("dataset_rows_admitted") == 0
            and registry.get("data_use_state", {}).get("labels_created") == 0
        ),
    }
    for name, passed in checks.items():
        if not passed:
            errors.append(f"evidence check failed: {name}")

    if pbc05_state.get("actual_attempts") != 3 or pbc05_state.get("instrumented_attempts") != 2:
        errors.append("PBC05 attempt count does not match the three pinned result snapshots")
    if pbc08_state.get("result_artifacts_referencing_row") != 3:
        errors.append("PBC08 row should appear in all three result snapshots, including one skipped row")
    safety = registry.get("safety_contract", {})
    if safety.get("network_operations") != 0 or safety.get("candidate_domain_access_operations") != 0:
        errors.append("closeout must report zero network and candidate-domain operations")
    if safety.get("labels_created") != 0 or safety.get("training_allowed") is not False:
        errors.append("label and training gates must remain closed")

    return {
        "analysis_id": "ISI_PBC05_PBC08_OFFLINE_CLOSEOUT_V2_QA",
        "created_at": registry.get("created_at"),
        "status": "PASS_RESULT_HISTORY_RECONCILED_NO_CAUSE_OVERCLAIMED" if not errors else "FAIL",
        "inputs": [
            {"role": "closeout_registry", "path": str(registry_path), "sha256": sha256_file(registry_path)},
            *checked_inputs,
            *documents,
        ],
        "checks": checks,
        "attempt_counts": {"PBC05_actual": 3, "PBC08_actual": 2, "PBC08_skipped_in_first_snapshot": True},
        "decision": {
            "offline_closeout_verified": not errors,
            "exact_historic_failure_causes_recovered": False,
            "same_release_retry_allowed": False,
            "new_source_request_created": False,
            "dataset_rows_admitted": 0,
            "labels_created": 0,
            "training_allowed": False,
        },
        "errors": errors,
        "safety_contract": {
            "network_operations": 0,
            "candidate_domain_access_operations": 0,
            "labels_created": 0,
            "training_allowed": False,
        },
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--qa-output", type=Path, default=QA_OUTPUT)
    args = parser.parse_args()
    result = verify(args.registry)
    if args.qa_output.exists():
        raise FileExistsError(f"Refusing to overwrite QA output: {args.qa_output}")
    args.qa_output.parent.mkdir(parents=True, exist_ok=True)
    with args.qa_output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"].startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
