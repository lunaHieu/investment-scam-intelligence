"""Materialize a frozen, metadata-only supplement of official Crimson source facts."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/crimson_official_source_followup_v2.json"
REGISTRY = ROOT / "registry/analyses/crimson_official_source_followup_v2.json"


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
    evidence_path = Path(config["evidence_output"])
    status_path = Path(config["access_status_output"])
    planned = [evidence_path, status_path, REGISTRY]
    existing = [str(path) for path in planned if path.exists()]
    if existing:
        raise FileExistsError("Refusing to overwrite frozen output(s): " + ", ".join(existing))

    evidence = config["evidence_records"]
    statuses = config["access_status"]
    write_jsonl_exclusive(evidence_path, evidence)
    write_jsonl_exclusive(status_path, statuses)

    materializer = ROOT / "scripts/materialize_crimson_official_source_followup_v2.py"
    registry = {
        "analysis_id": "ISI_CRIMSON_OFFICIAL_SOURCE_FOLLOWUP_V2",
        "created_at": config["created_at"],
        "status": "PASS_OFFICIAL_SOURCE_FACTS_PINNED_REVIEW_AND_ADMISSION_OPEN",
        "inputs": [
            {"role": "frozen_workflow_config", "path": str(config_path), "sha256": sha256_file(config_path)}
        ],
        "implementation": [
            {"role": "materializer", "path": "scripts/materialize_crimson_official_source_followup_v2.py", "sha256": sha256_file(materializer)}
        ],
        "outputs": [
            {"role": "official_source_fact_supplement", "path": str(evidence_path), "sha256": sha256_file(evidence_path), "record_count": len(evidence)},
            {"role": "official_source_access_status_supplement", "path": str(status_path), "sha256": sha256_file(status_path), "record_count": len(statuses)}
        ],
        "counts": {
            "official_source_fact_rows": len(evidence),
            "unique_candidate_pilots_with_new_direct_source_facts": len({row["pilot_id"] for row in evidence}),
            "unique_direct_official_pages_read": len({row["official_source_url"] for row in evidence}),
            "followup_status_rows": len(statuses),
            "primary_review_tasks_completed": 0,
            "independent_second_reviews_completed": 0,
            "labels_created": 0,
            "dataset_rows_admitted": 0
        },
        "decision": {
            "official_fact_collection_only": True,
            "all_15_followup_primary_reviews_remain_pending": True,
            "root_only_or_name_only_matches_resolved": False,
            "blind_second_review_may_be_performed_by_this_primary_evidence_pass": False,
            "data_admission_allowed": False,
            "label_materialization_allowed": False,
            "training_allowed": False
        },
        "safety_contract": {
            "network_operations": 0,
            "official_reference_page_reads": len({row["official_source_url"] for row in evidence}),
            "candidate_domain_access_operations": 0,
            "raw_official_page_files_retained": 0,
            "labels_created": 0,
            "dataset_rows_admitted": 0,
            "validation_or_test_opened": False,
            "model_scoring_or_training_performed": False,
            "training_allowed": False
        }
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
