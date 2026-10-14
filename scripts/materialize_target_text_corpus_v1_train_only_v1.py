"""Materialize the verified V1-Core train-only dataset and audit report."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.build_target_text_corpus_v1_group_split_plan_v1 import canonical, sha256_value
from scripts.verify_target_text_corpus_v1_core_release_v1 import load_object, sha256_file
from scripts.verify_target_text_corpus_v1_train_materialization_release_v1 import verify as verify_release


def dataset_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows).encode("utf-8")


def materialize(release_path: Path, release_qa_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any], bytes]:
    release = load_object(release_path)
    release_qa = load_object(release_qa_path)
    expected_qa = verify_release(release_path, require_outputs_absent=False)
    if canonical(release_qa) != canonical(expected_qa):
        raise ValueError("Train-materialization release QA differs from independent recomputation")
    contract = load_object(Path(release["inputs"]["contract"]["path"]))
    if release_qa.get("status") != contract["release_qa_status"]:
        raise ValueError("Train-materialization release QA did not pass")
    if release_qa.get("inputs", {}).get("release_sha256") != sha256_file(release_path):
        raise ValueError("Train-materialization release QA binding mismatch")
    if release_qa.get("decision", {}).get("materialization_execution_allowed") is not True:
        raise ValueError("Train-materialization execution remains closed")

    manifest_ref = release["inputs"]["core_release_manifest"]
    manifest_path = Path(manifest_ref["path"])
    if not manifest_path.is_file() or sha256_file(manifest_path) != manifest_ref["sha256"]:
        raise ValueError("Core-release manifest path or hash mismatch")
    manifest = load_object(manifest_path)
    source_by_id = {str(row["record_id"]): row for row in manifest.get("records", [])}
    release_records = list(release.get("records", []))
    release_ids = [str(row.get("record_id")) for row in release_records]
    if len(release_ids) != len(set(release_ids)) or len(release_ids) != contract["expected_train_records"]:
        raise ValueError("Train release record population is invalid")

    rows: list[dict[str, Any]] = []
    audit_index: list[dict[str, Any]] = []
    for item in release_records:
        record_id = str(item["record_id"])
        source = source_by_id.get(record_id)
        if source is None or source.get("cohort") != "DEVELOPMENT":
            raise ValueError(f"Train source record is missing or not development: {record_id}")
        if sha256_value(source) != item["record_commitment_sha256"]:
            raise ValueError(f"Train source record commitment mismatch: {record_id}")
        if source.get("target_status") != item["target_status"] or source.get("channel_id") != item["channel_id"] or source.get("transitive_group_id") != item["group_id"]:
            raise ValueError(f"Train source metadata mismatch: {record_id}")
        if contract["label_mapping"].get(source["target_status"]) != item["label"]:
            raise ValueError(f"Train label mapping mismatch: {record_id}")
        row = {
            "record_id": record_id,
            "text_content": source["observed_artifact_visible_text"],
            "label": item["label"],
            "group_id": item["group_id"],
        }
        if set(row) != set(contract["dataset_fields"]):
            raise ValueError(f"Train dataset schema mismatch: {record_id}")
        rows.append(row)
        audit_index.append({
            "record_id": record_id,
            "target_status": item["target_status"],
            "channel_id": item["channel_id"],
            "group_id": item["group_id"],
            "record_commitment_sha256": item["record_commitment_sha256"],
        })

    payload = dataset_bytes(rows)
    label_counts = Counter(str(item["target_status"]) for item in release_records)
    channel_counts = Counter(str(item["channel_id"]) for item in release_records)
    report = {
        "dataset_id": contract["dataset_id"],
        "status": contract["dataset_status"],
        "inputs": {
            "release_sha256": sha256_file(release_path),
            "release_qa_sha256": sha256_file(release_qa_path),
            "core_release_manifest_sha256": sha256_file(manifest_path),
        },
        "output": {
            "dataset_path": release["outputs"]["dataset"],
            "dataset_sha256": hashlib.sha256(payload).hexdigest(),
        },
        "summary": {
            "record_count": len(rows),
            "label_counts": dict(sorted(label_counts.items())),
            "channel_counts": dict(sorted(channel_counts.items())),
            "validation_records": 0,
            "internal_test_records": 0,
            "external_holdout_records": 0,
        },
        "audit_index": audit_index,
        "decision": {
            "train_only_dataset_materialized": True,
            "model_development_protocol_required": True,
            "training_allowed_now": False,
            "validation_opening_allowed": False,
            "internal_test_opening_allowed": False,
            "external_holdout_opening_allowed": False,
        },
        "safety_contract": {"network_operations": 0, "model_operations": 0, "training_operations": 0, "validation_or_test_openings": 0},
    }
    return rows, report, payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-qa", type=Path, required=True)
    args = parser.parse_args()
    release = load_object(args.release)
    dataset_path = Path(release["outputs"]["dataset"])
    report_path = Path(release["outputs"]["report"])
    for path in (dataset_path, report_path):
        if path.exists() or path.with_suffix(path.suffix + ".partial").exists():
            raise FileExistsError(f"Refusing to overwrite train materialization output: {path}")
    _, report, payload = materialize(args.release, args.release_qa)
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    dataset_partial = dataset_path.with_suffix(dataset_path.suffix + ".partial")
    report_partial = report_path.with_suffix(report_path.suffix + ".partial")
    dataset_partial.write_bytes(payload)
    report_partial.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    dataset_partial.replace(dataset_path)
    report_partial.replace(report_path)
    print(json.dumps({"dataset_id": report["dataset_id"], "summary": report["summary"], "dataset": str(dataset_path), "dataset_sha256": sha256_file(dataset_path), "report": str(report_path), "report_sha256": sha256_file(report_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
