"""Materialize an exclusive, one-record official-source addendum for Crimson."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/crimson_official_source_followup_v3.json"
REGISTRY = ROOT / "registry/analyses/crimson_official_source_followup_v3.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_jsonl_exclusive(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            stream.write("\n")


def write_json_exclusive(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def materialize(config_path: Path = CONFIG) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    prior_path = ROOT / config["prior_supplement_registry"]["path"]
    if not prior_path.is_file() or sha256_file(prior_path) != config["prior_supplement_registry"]["sha256"]:
        raise ValueError("Pinned V2 official-source supplement registry is missing or changed")

    evidence_path = Path(config["evidence_output"])
    status_path = Path(config["access_status_output"])
    planned = [evidence_path, status_path, REGISTRY]
    existing = [str(path) for path in planned if path.exists()]
    if existing:
        raise FileExistsError("Refusing to overwrite frozen output(s): " + ", ".join(existing))

    evidence = config["evidence_records"]
    statuses = config["access_status"]
    if len(evidence) != 1 or len(statuses) != 1:
        raise ValueError("V3 is a frozen single-record source addendum")
    write_jsonl_exclusive(evidence_path, evidence)
    write_jsonl_exclusive(status_path, statuses)

    materializer = ROOT / "scripts/materialize_crimson_official_source_followup_v3.py"
    registry = {
        "analysis_id": "ISI_CRIMSON_OFFICIAL_SOURCE_FOLLOWUP_V3",
        "created_at": config["created_at"],
        "status": "PASS_ALTERNATE_OFFICIAL_FACT_PINNED_PRIMARY_REVIEW_STILL_PENDING",
        "inputs": [
            {"role": "frozen_workflow_config", "path": "configs/crimson_official_source_followup_v3.json", "sha256": sha256_file(config_path)},
            {"role": "prior_v2_supplement_registry", "path": config["prior_supplement_registry"]["path"], "sha256": sha256_file(prior_path)},
        ],
        "implementation": [
            {"role": "materializer", "path": "scripts/materialize_crimson_official_source_followup_v3.py", "sha256": sha256_file(materializer)}
        ],
        "source": {
            "title": evidence[0]["source_title"],
            "url": evidence[0]["official_source_url"],
            "publication_date": evidence[0]["source_publication_date"],
            "retrieved_on": evidence[0]["retrieved_on"],
            "access_mode": evidence[0]["access_mode"],
            "raw_page_retained": False,
        },
        "outputs": [
            {"role": "official_source_fact_addendum", "path": str(evidence_path), "sha256": sha256_file(evidence_path), "record_count": len(evidence)},
            {"role": "official_source_access_status_addendum", "path": str(status_path), "sha256": sha256_file(status_path), "record_count": len(statuses)},
        ],
        "counts": {
            "new_fact_rows": 1,
            "pilot_ids_with_new_direct_facts": 1,
            "direct_official_documents_read": 1,
            "primary_reviews_completed": 0,
            "independent_second_reviews_completed": 0,
            "labels_created": 0,
            "dataset_rows_admitted": 0,
            "training_eligible": 0,
        },
        "decision": {
            "source_fact_collection_only": True,
            "pilot_crimson_ref_016_primary_review_completed": False,
            "previously_blocked_url_retried": False,
            "candidate_domain_access_allowed": False,
            "data_admission_allowed": False,
            "label_materialization_allowed": False,
            "training_allowed": False,
        },
        "safety_contract": {
            "network_operations": 0,
            "official_reference_documents_read_before_materialization": 1,
            "candidate_domain_access_operations": 0,
            "previously_blocked_url_retries": 0,
            "raw_official_page_files_retained": 0,
            "labels_created": 0,
            "dataset_rows_admitted": 0,
            "training_allowed": False,
        },
    }
    write_json_exclusive(REGISTRY, registry)
    return registry


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    result = materialize()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
