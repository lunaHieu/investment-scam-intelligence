"""Independently verify the frozen one-record Crimson source addendum."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/crimson_official_source_followup_v3.json"
REGISTRY = ROOT / "registry/analyses/crimson_official_source_followup_v3.json"
QA_OUTPUT = ROOT / "registry/analyses/crimson_official_source_followup_v3_qa.json"
MATERIALIZER_REL = "scripts/materialize_crimson_official_source_followup_v3.py"


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
    config_hash = sha256_file(config_path)
    prior = ROOT / config["prior_supplement_registry"]["path"]
    prior_hash = sha256_file(prior) if prior.is_file() else None
    if prior_hash != config["prior_supplement_registry"]["sha256"]:
        errors.append("pinned V2 source supplement registry is missing or changed")
    if registry.get("analysis_id") != "ISI_CRIMSON_OFFICIAL_SOURCE_FOLLOWUP_V3":
        errors.append("unexpected source addendum analysis id")
    if not any(item.get("path") == "configs/crimson_official_source_followup_v3.json" and item.get("sha256") == config_hash for item in registry.get("inputs", [])):
        errors.append("workflow config hash is not pinned")
    if not any(item.get("path") == MATERIALIZER_REL and item.get("sha256") == sha256_file(ROOT / MATERIALIZER_REL) for item in registry.get("implementation", [])):
        errors.append("materializer hash is not pinned")

    facts = config.get("evidence_records", [])
    statuses = config.get("access_status", [])
    output_specs = {item.get("role"): item for item in registry.get("outputs", [])}
    expected = {
        "official_source_fact_addendum": (Path(config["evidence_output"]), facts),
        "official_source_access_status_addendum": (Path(config["access_status_output"]), statuses),
    }
    if set(output_specs) != set(expected):
        errors.append("registered output roles differ from frozen config")
    output_checks: list[dict[str, Any]] = []
    for role, (path, expected_rows) in expected.items():
        if not path.is_file():
            errors.append(f"missing output: {role}")
            continue
        rows = load_jsonl(path)
        digest = sha256_file(path)
        spec = output_specs.get(role, {})
        if rows != expected_rows:
            errors.append(f"output rows differ from frozen config: {role}")
        if digest != spec.get("sha256") or len(rows) != spec.get("record_count"):
            errors.append(f"output hash/count mismatch: {role}")
        output_checks.append({"role": role, "path": str(path), "sha256": digest, "record_count": len(rows)})

    if len(facts) != 1 or len(statuses) != 1:
        errors.append("V3 must contain exactly one fact and one access-status row")
    if facts:
        row = facts[0]
        hostname = (urlparse(str(row.get("official_source_url"))).hostname or "").lower()
        if hostname != "www.consob.it" or hostname not in {host.lower() for host in config.get("allowed_official_hostnames", [])}:
            errors.append("source URL host is not the frozen official Consob host")
        if row.get("pilot_id") != "PILOT_CRIMSON_REF_016" or row.get("candidate_host") != "magnomicyieldltd.com":
            errors.append("fact does not match the exact frozen Magnomic task")
        if row.get("access_mode") != "DIRECT_OFFICIAL_DOCUMENT_READ" or row.get("domain_match_scope") != "EXACT_DOMAIN":
            errors.append("direct document access or exact-host scope is not recorded")
        if row.get("human_primary_review_status") != "PENDING" or row.get("identity_relationship") != "UNREVIEWED":
            errors.append("source fact was incorrectly promoted to a human review")
        if row.get("model_label_disposition") != "UNCERTAIN" or row.get("label_created") is not False:
            errors.append("label disposition changed")
        if row.get("data_admission_allowed") is not False or row.get("training_eligible") != "NO" or row.get("raw_page_retained") is not False:
            errors.append("data admission, training, or raw-page-retention gate changed")
    if statuses:
        status = statuses[0]
        if status.get("previous_blocked_reference_retried") is not False or status.get("primary_review_status") != "PENDING":
            errors.append("blocked-URL retry or primary-review state is inconsistent")
        if status.get("model_label_disposition") != "UNCERTAIN" or status.get("label_created") is not False or status.get("training_eligible") != "NO":
            errors.append("access-status addendum changed label/training state")

    safety = registry.get("safety_contract", {})
    if safety.get("network_operations") != 0 or safety.get("candidate_domain_access_operations") != 0 or safety.get("previously_blocked_url_retries") != 0:
        errors.append("offline materialization or candidate/blocked-URL safety contract failed")
    if safety.get("labels_created") != 0 or safety.get("dataset_rows_admitted") != 0 or safety.get("training_allowed") is not False:
        errors.append("label, admission, or training gates must remain closed")

    return {
        "verification_id": "ISI_CRIMSON_OFFICIAL_SOURCE_FOLLOWUP_V3_QA",
        "created_at": config.get("created_at"),
        "status": "PASS_ALTERNATE_OFFICIAL_FACT_PINNED_PRIMARY_REVIEW_STILL_PENDING" if not errors else "FAIL",
        "inputs": [
            {"role": "source_addendum_registry", "path": str(registry_path), "sha256": sha256_file(registry_path)},
            {"role": "workflow_config", "path": str(config_path), "sha256": config_hash},
            {"role": "prior_v2_registry", "path": config["prior_supplement_registry"]["path"], "sha256": prior_hash},
            {"role": "materializer", "path": MATERIALIZER_REL, "sha256": sha256_file(ROOT / MATERIALIZER_REL)},
        ],
        "checks": {
            "registered_outputs": output_checks,
            "fact_rows": len(facts),
            "pilot_ids_with_new_fact": len({row.get("pilot_id") for row in facts}),
            "direct_official_documents_read": 1 if facts else 0,
            "primary_reviews_completed": 0,
            "previously_blocked_url_retries": 0,
            "candidate_domain_accesses": 0,
            "labels_created": 0,
            "dataset_rows_admitted": 0,
            "training_eligible": 0,
        },
        "errors": errors,
        "decision": {
            "primary_review_required": True,
            "independent_second_review_required_where_planned": True,
            "data_admission_allowed": False,
            "label_materialization_allowed": False,
            "training_allowed": False,
        },
        "safety_contract": {
            "network_operations_during_verification": 0,
            "candidate_domain_access_operations": 0,
            "previously_blocked_url_retries": 0,
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
