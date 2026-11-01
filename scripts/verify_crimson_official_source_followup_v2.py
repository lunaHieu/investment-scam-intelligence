"""Independently verify the immutable Crimson official-source supplement."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/crimson_official_source_followup_v2.json"
REGISTRY = ROOT / "registry/analyses/crimson_official_source_followup_v2.json"
QA_OUTPUT = ROOT / "registry/analyses/crimson_official_source_followup_v2_qa.json"
MATERIALIZER_REL = "scripts/materialize_crimson_official_source_followup_v2.py"
EXPECTED_PILOTS = {
    "PILOT_CRIMSON_REF_012",
    "PILOT_CRIMSON_REF_013",
    "PILOT_CRIMSON_REF_026",
    "PILOT_CRIMSON_REF_028",
    "PILOT_CRIMSON_REF_011",
    "PILOT_CRIMSON_REF_017",
    "PILOT_CRIMSON_REF_019",
    "PILOT_CRIMSON_REF_034",
    "PILOT_CRIMSON_REF_014",
    "PILOT_CRIMSON_REF_033",
    "PILOT_CRIMSON_REF_021",
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
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"Expected JSON object at {path}:{number}")
            rows.append(value)
    return rows


def verify(config_path: Path = CONFIG, registry_path: Path = REGISTRY) -> dict[str, Any]:
    config = load_json(config_path)
    registry = load_json(registry_path)
    errors: list[str] = []

    if registry.get("analysis_id") != "ISI_CRIMSON_OFFICIAL_SOURCE_FOLLOWUP_V2":
        errors.append("unexpected official-source supplement analysis id")
    config_hash = sha256_file(config_path)
    if not any(
        item.get("role") == "frozen_workflow_config"
        and item.get("path") == str(config_path)
        and item.get("sha256") == config_hash
        for item in registry.get("inputs", [])
    ):
        errors.append("workflow config hash is not pinned")
    materializer = ROOT / MATERIALIZER_REL
    materializer_hash = sha256_file(materializer)
    if not any(
        item.get("path") == MATERIALIZER_REL and item.get("sha256") == materializer_hash
        for item in registry.get("implementation", [])
    ):
        errors.append("materializer hash is not pinned")

    output_specs = {item.get("role"): item for item in registry.get("outputs", [])}
    expected_specs = {
        "official_source_fact_supplement": (Path(config["evidence_output"]), config["evidence_records"]),
        "official_source_access_status_supplement": (Path(config["access_status_output"]), config["access_status"]),
    }
    if set(output_specs) != set(expected_specs):
        errors.append("registered output roles do not match the frozen config")
    artifacts: dict[str, list[dict[str, Any]]] = {}
    output_checks: list[dict[str, Any]] = []
    for role, (path, expected_rows) in expected_specs.items():
        spec = output_specs.get(role, {})
        if not path.is_file():
            errors.append(f"missing output: {role}")
            continue
        actual_hash = sha256_file(path)
        rows = load_jsonl(path)
        if actual_hash != spec.get("sha256") or len(rows) != spec.get("record_count"):
            errors.append(f"registered output hash/count mismatch: {role}")
        if rows != expected_rows:
            errors.append(f"output rows differ from the frozen config: {role}")
        artifacts[role] = rows
        output_checks.append({"role": role, "path": str(path), "sha256": actual_hash, "record_count": len(rows)})

    facts = artifacts.get("official_source_fact_supplement", [])
    statuses = artifacts.get("official_source_access_status_supplement", [])
    allowed_hosts = {value.lower() for value in config.get("allowed_official_hostnames", [])}
    fact_ids = [row.get("record_id") for row in facts]
    if len(facts) != 12 or len(fact_ids) != len(set(fact_ids)):
        errors.append("expected 12 unique official-source fact rows")
    if {row.get("pilot_id") for row in facts} != EXPECTED_PILOTS:
        errors.append("official fact pilot coverage differs from the frozen expected set")
    if len(statuses) != 15 or len({row.get("pilot_id") for row in statuses}) != 15:
        errors.append("expected all 15 unique official-source followup status rows")
    for row in facts:
        hostname = (urlparse(str(row.get("official_source_url"))).hostname or "").lower()
        if hostname not in allowed_hosts or row.get("access_mode") not in {
            "DIRECT_OFFICIAL_PAGE_READ",
            "DIRECT_OFFICIAL_DOCUMENT_READ",
        }:
            errors.append(f"source is not a directly read allowlisted official page: {row.get('record_id')}")
        if row.get("raw_page_retained") is not False:
            errors.append(f"raw page retention is not false: {row.get('record_id')}")
        if row.get("human_primary_review_status") != "PENDING":
            errors.append(f"a source fact was mistaken for a primary review: {row.get('record_id')}")
        if row.get("model_label_disposition") != "UNCERTAIN" or row.get("label_created") is not False:
            errors.append(f"a source fact changed the label state: {row.get('record_id')}")
        if row.get("data_admission_allowed") is not False or row.get("training_eligible") != "NO":
            errors.append(f"a source fact opened data/training eligibility: {row.get('record_id')}")
    for row in statuses:
        if row.get("same_url_retry_performed") is not False or row.get("primary_review_status") != "PENDING":
            errors.append(f"followup status violates retry/review boundary: {row.get('pilot_id')}")
        if row.get("model_label_disposition", "UNCERTAIN") != "UNCERTAIN":
            errors.append(f"followup status contains a non-UNCERTAIN disposition: {row.get('pilot_id')}")
    root_only = {row["pilot_id"] for row in facts if row.get("domain_match_scope") == "ROOT_DOMAIN_ONLY"}
    if root_only != {"PILOT_CRIMSON_REF_026", "PILOT_CRIMSON_REF_028", "PILOT_CRIMSON_REF_021"}:
        errors.append("root-only domain relation boundaries differ from the frozen expected set")
    if any(row.get("domain_match_scope") == "ENTITY_NAME_ONLY" and row.get("identity_relationship") != "UNCLEAR" for row in facts):
        errors.append("entity-name-only evidence cannot establish candidate identity")

    safety = registry.get("safety_contract", {})
    if safety.get("network_operations") != 0 or safety.get("candidate_domain_access_operations") != 0:
        errors.append("candidate/data network access safety counts must remain zero")
    if safety.get("labels_created") != 0 or safety.get("dataset_rows_admitted") != 0 or safety.get("training_allowed") is not False:
        errors.append("labels, dataset admission, and training must remain closed")
    decision = registry.get("decision", {})
    if decision.get("all_15_followup_primary_reviews_remain_pending") is not True:
        errors.append("primary followup tasks must remain pending")
    if decision.get("data_admission_allowed") is not False or decision.get("label_materialization_allowed") is not False:
        errors.append("source collection must not admit or label data")

    return {
        "verification_id": "ISI_CRIMSON_OFFICIAL_SOURCE_FOLLOWUP_V2_QA",
        "created_at": config.get("created_at"),
        "status": "PASS_OFFICIAL_FACTS_PINNED_REVIEW_AND_ADMISSION_STILL_CLOSED" if not errors else "FAIL",
        "inputs": [
            {"role": "official_source_followup_registry", "path": str(registry_path), "sha256": sha256_file(registry_path)},
            {"role": "workflow_config", "path": str(config_path), "sha256": config_hash},
            {"role": "materializer", "path": MATERIALIZER_REL, "sha256": materializer_hash},
        ],
        "checks": {
            "registered_outputs": output_checks,
            "official_source_fact_rows": len(facts),
            "unique_pilots_with_new_facts": len({row.get("pilot_id") for row in facts}),
            "unique_official_pages_directly_read": len({row.get("official_source_url") for row in facts}),
            "followup_status_rows": len(statuses),
            "primary_reviews_completed": 0,
            "independent_second_reviews_completed": 0,
            "root_only_relationships_kept_unresolved": len(root_only),
            "same_url_retries": 0,
            "candidate_domain_accesses": 0,
            "labels_created": 0,
            "dataset_rows_admitted": 0,
            "training_eligible": 0,
        },
        "errors": errors,
        "decision": {
            "primary_review_required": True,
            "independent_second_review_required_where_planned": True,
            "reconciliation_performed": False,
            "data_admission_allowed": False,
            "label_materialization_allowed": False,
            "training_allowed": False,
        },
        "safety_contract": {
            "network_operations_during_verification": 0,
            "candidate_domain_access_operations": 0,
            "raw_official_page_files_retained": 0,
            "labels_created": 0,
            "dataset_rows_admitted": 0,
            "training_allowed": False,
        },
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    result = verify()
    if QA_OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite QA output: {QA_OUTPUT}")
    QA_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with QA_OUTPUT.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"].startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
