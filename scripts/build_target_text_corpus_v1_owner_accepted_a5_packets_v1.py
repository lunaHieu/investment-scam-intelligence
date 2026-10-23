"""Build separate exact-42 A5 language-review and fresh-cohort packets offline."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


EXPECTED_PROTOCOL_ID = "ISI_TARGET_TEXT_CORPUS_V1_OWNER_ACCEPTED_A5_PACKET_PROTOCOL_V1"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _resolved(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return ("".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)).encode("utf-8")


def validate_protocol(config_path: Path) -> tuple[dict[str, Any], dict[str, Path]]:
    config = load_object(config_path)
    if config.get("protocol_id") != EXPECTED_PROTOCOL_ID:
        raise ValueError("Unexpected A5 packet protocol")
    root = config_path.resolve().parents[1]
    paths: dict[str, Path] = {}
    for item in config["inputs"]:
        path = _resolved(root, item["path"])
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise ValueError(f"A5 input mismatch: {item['role']}")
        paths[item["role"]] = path
    a4 = load_object(paths["a4_registry"])
    a4_qa = load_object(paths["a4_independent_qa"])
    if not a4.get("decision", {}).get("language_review_packet_may_be_prepared") or not a4.get("decision", {}).get("fresh_cohort_assertion_packet_may_be_prepared"):
        raise PermissionError("A4 did not open both A5 packet-preparation gates")
    if a4_qa.get("status") != "PASS_READINESS_REPORT_FULLY_RECOMPUTED":
        raise PermissionError("A4 independent QA did not pass")
    for gate in (
        "repaired_candidate_manifest_allowed", "partial_channel_contribution_allowed", "network_access_allowed",
        "candidate_domain_access_allowed", "labeling_allowed", "validation_or_test_opening_allowed",
        "model_scoring_allowed", "training_allowed",
    ):
        if config["decision"].get(gate) is not False:
            raise PermissionError(f"A5 protocol opened forbidden gate: {gate}")
    language = config["language_review_contract"]
    if language.get("human_review_required") is not True or language.get("builder_may_set_language_code") is not False or language.get("builder_may_set_human_reviewed_language_true") is not False:
        raise PermissionError("A5 language packet may fabricate a human review")
    fresh = config["fresh_cohort_contract"]
    if fresh.get("admission_credit_now") != 0 or fresh.get("release_record_materialization_allowed") is not False:
        raise PermissionError("A5 fresh-cohort packet grants premature admission credit")
    return config, paths


def build_packets(config_path: Path) -> dict[str, Any]:
    config, paths = validate_protocol(config_path)
    owner = load_object(paths["owner_accepted_records"])
    owner_rows = list(owner.get("records", []))
    ids = [str(row.get("record_id", "")) for row in owner_rows]
    population = config["population_contract"]
    digest = hashlib.sha256(json.dumps(ids, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
    counts = Counter(str(row.get("cohort")) for row in owner_rows)
    if len(ids) != population["record_count"] or len(ids) != len(set(ids)) or digest != population["ordered_record_ids_sha256"]:
        raise ValueError("A5 owner-accepted population identity changed")
    if counts != {"DEVELOPMENT": population["development_count"], "EXTERNAL_HOLDOUT": population["external_holdout_count"]}:
        raise ValueError("A5 cohort counts changed")
    if any(row.get("ground_truth_status") != population["target_status"] or row.get("label_created") is not True for row in owner_rows):
        raise ValueError("A5 owner-accepted label state changed")

    exact = {str(row["record_id"]): row for row in _read_jsonl(paths["exact_text_manifest"])}
    grouping = {str(row["record_id"]): row for row in load_object(paths["post_capture_grouping"])["records"]}
    manual = {str(row["record_id"]): row for row in load_object(paths["manual_group_review"])["records"]}
    language_rows: list[dict[str, Any]] = []
    fresh_rows: list[dict[str, Any]] = []
    for index, owner_row in enumerate(owner_rows, start=1):
        record_id = str(owner_row["record_id"])
        if record_id not in exact or record_id not in grouping or record_id not in manual:
            raise ValueError(f"A5 evidence missing: {record_id}")
        text_row = exact[record_id]
        group_row = grouping[record_id]
        manual_row = manual[record_id]
        text_path = Path(str(text_row["text_path"]))
        if not text_path.is_file() or sha256_file(text_path) != text_row["text_sha256"]:
            raise ValueError(f"A5 visible-text byte mismatch: {record_id}")
        if text_row.get("cohort") != owner_row.get("cohort") or group_row.get("cohort") != owner_row.get("cohort"):
            raise ValueError(f"A5 cohort evidence mismatch: {record_id}")
        opened = group_row.get("opened_overlap")
        if not isinstance(opened, dict) or not opened or any(values for values in opened.values()):
            raise ValueError(f"A5 opened-cohort overlap is not clear: {record_id}")
        if group_row.get("cross_cohort_group_collision") is not False:
            raise ValueError(f"A5 cross-cohort collision: {record_id}")
        if manual_row.get("group_decision") != config["fresh_cohort_contract"]["manual_group_decision_required"]:
            raise ValueError(f"A5 manual grouping is not provisionally distinct: {record_id}")
        namespace = config["fresh_cohort_contract"]["required_acquisition_namespace"]
        if not record_id.startswith(namespace + "_") or text_row.get("availability_plan_id") != record_id:
            raise ValueError(f"A5 fresh acquisition namespace mismatch: {record_id}")

        language_rows.append({
            "review_item_id": f"A5_LANGUAGE_{index:03d}",
            "record_id": record_id,
            "cohort": owner_row["cohort"],
            "source_text_path": str(text_path.resolve()),
            "source_text_sha256": text_row["text_sha256"],
            "non_whitespace_text_characters": text_row["non_whitespace_text_characters"],
            "automatic_language_hint": None,
            "language_code": None,
            "human_reviewed_language": False,
            "review_status": config["language_review_contract"]["initial_review_status"],
            "ground_truth_status_changed": False,
            "admission_credit_now": 0,
        })
        fresh_rows.append({
            "assertion_item_id": f"A5_FRESH_{index:03d}",
            "record_id": record_id,
            "cohort": owner_row["cohort"],
            "acquisition_namespace": namespace,
            "availability_plan_id": text_row["availability_plan_id"],
            "shortlist_id": text_row["shortlist_id"],
            "source_text_sha256": text_row["text_sha256"],
            "raw_capture_sha256": text_row["raw_capture_sha256"],
            "opened_overlap_clear": True,
            "cross_cohort_group_collision": False,
            "manual_group_decision": manual_row["group_decision"],
            "fresh_cohort": config["fresh_cohort_contract"]["assertion_value"],
            "assertion_status": "ASSERTED_FROM_HASH_BOUND_ACQUISITION_AND_EXCLUSION_EVIDENCE",
            "release_record_materialized": False,
            "admission_credit_now": 0,
        })

    protocol_hash = sha256_file(config_path)
    language_packet_hash = hashlib.sha256(_jsonl_bytes(language_rows)).hexdigest()
    fresh_packet_hash = hashlib.sha256(_jsonl_bytes(fresh_rows)).hexdigest()
    language_report = {
        "report_id": "ISI_TARGET_TEXT_CORPUS_V1_A5_LANGUAGE_REVIEW_PACKET_REPORT_V1",
        "status": "PASS_EXACT_42_LANGUAGE_REVIEW_PACKET_PREPARED_HUMAN_DECISIONS_PENDING",
        "protocol_sha256": protocol_hash,
        "packet_sha256": language_packet_hash,
        "population": {"ordered_record_ids_sha256": digest, "records": len(ids), "development": counts["DEVELOPMENT"], "external_holdout": counts["EXTERNAL_HOLDOUT"]},
        "review_state": {"pending_human_review": len(ids), "completed_human_review": 0, "language_codes_materialized": 0, "automatic_hints_used_as_final": 0},
        "decision": {"human_review_still_required": True, "admission_credit_now": 0, "candidate_manifest_created": False, "training_allowed": False},
        "safety_contract": {"network_operations": 0, "labels_changed": 0, "model_operations": 0, "training_allowed": False},
    }
    fresh_report = {
        "report_id": "ISI_TARGET_TEXT_CORPUS_V1_A5_FRESH_COHORT_ASSERTION_REPORT_V1",
        "status": "PASS_EXACT_42_FRESH_COHORT_ASSERTIONS_PREPARED_NO_ADMISSION_CREDIT",
        "protocol_sha256": protocol_hash,
        "packet_sha256": fresh_packet_hash,
        "population": {"ordered_record_ids_sha256": digest, "records": len(ids), "development": counts["DEVELOPMENT"], "external_holdout": counts["EXTERNAL_HOLDOUT"]},
        "assertion_state": {"fresh_cohort_asserted": len(ids), "opened_overlap_clear": len(ids), "cross_cohort_collision_free": len(ids), "manual_provisionally_distinct": len(ids)},
        "decision": {"packet_assertions_ready_for_independent_qa": True, "release_records_materialized": 0, "admission_credit_now": 0, "training_allowed": False},
        "safety_contract": {"network_operations": 0, "labels_changed": 0, "model_operations": 0, "training_allowed": False},
    }
    return {"language_rows": language_rows, "language_report": language_report, "fresh_rows": fresh_rows, "fresh_report": fresh_report}


def _write_new(path: Path, payload: bytes) -> None:
    partial = path.with_suffix(path.suffix + ".partial")
    if path.exists() or partial.exists():
        raise FileExistsError(f"Refusing to overwrite A5 output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    partial.write_bytes(payload)
    partial.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    result = build_packets(args.config)
    config = load_object(args.config)
    if args.verify_only:
        print(json.dumps({"language": result["language_report"], "fresh": result["fresh_report"]}, ensure_ascii=False, indent=2))
        return 0
    outputs = config["planned_outputs"]
    paths = {key: Path(value) for key, value in outputs.items() if key in {"language_packet", "language_report", "fresh_packet", "fresh_report"}}
    if any(path.exists() or path.with_suffix(path.suffix + ".partial").exists() for path in paths.values()):
        raise FileExistsError("Refusing to overwrite an A5 packet or report")
    _write_new(paths["language_packet"], _jsonl_bytes(result["language_rows"]))
    _write_new(paths["language_report"], (json.dumps(result["language_report"], ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    _write_new(paths["fresh_packet"], _jsonl_bytes(result["fresh_rows"]))
    _write_new(paths["fresh_report"], (json.dumps(result["fresh_report"], ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({key: {"path": str(path), "sha256": sha256_file(path)} for key, path in paths.items()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
