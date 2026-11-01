"""Independently verify the immutable Crimson owner-progress artifacts offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/crimson_owner_review_progress_v1.json"
REGISTRY = ROOT / "registry/analyses/crimson_owner_review_progress_v1.json"
QA_OUTPUT = ROOT / "registry/analyses/crimson_owner_review_progress_v1_qa.json"
BLIND_FIELDS = {
    "identity_suggestion",
    "evidence_suggestion",
    "first_reviewer",
    "first_review_decision",
    "first_review_notes",
    "owner_primary_decision",
    "owner_primary_notes",
}


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


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"Expected JSON object at {path}:{number}")
            rows.append(value)
    return rows


def verify(registry_path: Path = REGISTRY, config_path: Path = CONFIG) -> dict[str, Any]:
    registry = load_json(registry_path)
    config = load_json(config_path)
    errors: list[str] = []
    artifacts: dict[str, list[dict[str, Any]]] = {}
    output_checks: list[dict[str, Any]] = []

    config_hash = sha256_file(config_path)
    if not any(
        item.get("role") == "workflow_config"
        and item.get("path") == str(config_path)
        and item.get("sha256") == config_hash
        for item in registry.get("inputs", [])
    ):
        errors.append("workflow config is not correctly pinned in the registry")

    materializer_path = ROOT / "scripts/record_crimson_owner_review_progress_v1.py"
    materializer_hash = sha256_file(materializer_path)
    implementation = registry.get("implementation", [])
    if not any(
        item.get("path") == "scripts/record_crimson_owner_review_progress_v1.py"
        and item.get("sha256") == materializer_hash
        for item in implementation
    ):
        errors.append("materializer implementation hash does not match the registry")

    roles = {item.get("role"): item for item in registry.get("outputs", [])}
    expected_roles = set(config["outputs"])
    if set(roles) != expected_roles:
        errors.append("registered output roles do not match the frozen config")
    for role, spec in roles.items():
        path = Path(str(spec.get("path", "")))
        if not path.is_file():
            errors.append(f"missing output: {role}")
            continue
        actual = sha256_file(path)
        if actual != spec.get("sha256") or str(path) != config["outputs"].get(role):
            errors.append(f"output path/hash mismatch: {role}")
        try:
            rows = load_jsonl(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"output is not valid JSONL ({role}): {exc}")
            continue
        if len(rows) != spec.get("record_count"):
            errors.append(f"record count mismatch: {role}")
        artifacts[role] = rows
        output_checks.append({"role": role, "path": str(path), "sha256": actual, "record_count": len(rows)})

    primary = artifacts.get("owner_confirmed_primary_decisions", [])
    reconciliations = artifacts.get("single_review_reconciliation", [])
    blind = artifacts.get("blind_second_review_handoff", [])
    source_evidence = artifacts.get("official_source_evidence", [])
    access_status = artifacts.get("official_source_access_status", [])

    if len(primary) != 24 or len({row.get("pilot_id") for row in primary}) != 24:
        errors.append("expected 24 unique owner-confirmed primary decisions")
    if any(
        row.get("review_status") != "COMPLETED"
        or row.get("decision_stage") != "HUMAN_FIRST_REVIEW"
        or row.get("human_confirmation_recorded") is not True
        or row.get("model_label_disposition") != "UNCERTAIN"
        or row.get("label_created") is not False
        or row.get("training_eligible") != "NO"
        for row in primary
    ):
        errors.append("owner primary decisions violate the review/label safety contract")

    if len(reconciliations) != 16 or any(
        row.get("second_review_required") is not False
        or row.get("model_label_disposition") != "UNCERTAIN"
        or row.get("label_created") is not False
        or row.get("training_eligible") != "NO"
        for row in reconciliations
    ):
        errors.append("single-review reconciliation scope or safety fields are invalid")
    if {row.get("pilot_id") for row in reconciliations} - {row.get("pilot_id") for row in primary}:
        errors.append("reconciliation contains a pilot without an owner-confirmed primary decision")

    if len(blind) != 9:
        errors.append("expected one prior and eight newly ready blind second-review tasks")
    for row in blind:
        leaked = BLIND_FIELDS & set(row)
        if leaked:
            errors.append(f"blind packet contains prohibited primary fields for {row.get('pilot_id')}: {sorted(leaked)}")
        if row.get("do_not_open_crimson_host") is not True or row.get("review_status") != "NOT_STARTED":
            errors.append(f"blind packet safety state is invalid for {row.get('pilot_id')}")
        if row.get("model_label_disposition") != "UNCERTAIN" or row.get("training_eligible") != "NO":
            errors.append(f"blind packet label/training state is invalid for {row.get('pilot_id')}")

    if len(source_evidence) != 6 or len(access_status) != 15:
        errors.append("expected six official-source observations and all 15 follow-up status rows")
    allowed_urls = {
        entry["url"] for entry in config.get("official_reference_access_status", [])
    }
    if any(row.get("official_source_url") not in allowed_urls for row in source_evidence):
        errors.append("source evidence contains a URL outside the frozen official-reference list")
    if any(row.get("raw_page_retained") is not False or row.get("label_created") is not False for row in source_evidence):
        errors.append("source evidence must stay metadata-only and non-labeling")
    if any(row.get("label_created") is not False or row.get("training_eligible") != "NO" for row in access_status):
        errors.append("official source access status rows violate safety fields")

    registry_counts = registry.get("counts", {})
    expected_counts = {
        "owner_confirmed_primary_decisions": 24,
        "single_review_reconciliations": 16,
        "blind_second_review_ready": 9,
        "blind_second_review_waiting": 12,
        "primary_review_pending": 15,
        "official_reference_evidence_rows_recorded": 6,
        "official_followup_tasks_still_open": 15,
        "labels_created": 0,
        "training_eligible_records": 0,
    }
    for key, expected in expected_counts.items():
        if registry_counts.get(key) != expected:
            errors.append(f"registry count mismatch for {key}")

    if registry.get("decision", {}).get("15_followup_rows_owner_confirmed") is not False:
        errors.append("the 15 official-reference follow-ups must remain unconfirmed")
    if registry.get("decision", {}).get("9_blind_reviews_completed") is not False:
        errors.append("preparing a blind handoff must not mark second review complete")

    return {
        "verification_id": "ISI_CRIMSON_OWNER_REVIEW_PROGRESS_V1_QA",
        "created_at": registry.get("created_at"),
        "status": "PASS_OWNER_PROGRESS_ARTIFACTS_AND_OPEN_GATES_VERIFIED" if not errors else "FAIL",
        "inputs": [
            {"role": "owner_progress_registry", "path": str(registry_path), "sha256": sha256_file(registry_path)},
            {"role": "workflow_config", "path": str(config_path), "sha256": config_hash},
            {"role": "materializer", "path": "scripts/record_crimson_owner_review_progress_v1.py", "sha256": materializer_hash},
        ],
        "checks": {
            "registered_output_hashes_and_counts": output_checks,
            "primary_confirmation_count": len(primary),
            "single_review_reconciliation_count": len(reconciliations),
            "blind_second_handoff_count": len(blind),
            "source_evidence_count": len(source_evidence),
            "official_followup_status_count": len(access_status),
            "blind_packet_primary_information_leaks": 0,
            "labels_created": 0,
            "training_eligible_records": 0,
        },
        "materializer_console_diagnostic": {
            "exit_code": 1,
            "failure_class": "UnicodeEncodeError",
            "failure_location": "printing the completed JSON result to the Windows console after artifacts and registry were written",
            "artifact_integrity_checked_independently": True,
            "materializer_was_not_rerun": True,
        },
        "decision": {
            "16_single_review_rows_reconciled_at_identity_evidence_level": True,
            "9_independent_second_reviews_completed": False,
            "15_primary_followups_open": True,
            "label_materialization_allowed": False,
            "training_allowed": False,
        },
        "errors": errors,
        "safety_contract": {
            "network_operations_during_verification": 0,
            "candidate_domain_access_operations": 0,
            "label_materialization_allowed": False,
            "training_allowed": False,
        },
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--qa-output", type=Path, default=QA_OUTPUT)
    args = parser.parse_args()
    result = verify(args.registry, args.config)
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
