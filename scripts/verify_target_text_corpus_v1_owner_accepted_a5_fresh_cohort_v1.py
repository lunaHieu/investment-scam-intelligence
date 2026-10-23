"""Independently verify the exact-42 A5 fresh-cohort assertion packet."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


EXPECTED_PROTOCOL_ID = "ISI_TARGET_TEXT_CORPUS_V1_OWNER_ACCEPTED_A5_PACKET_PROTOCOL_V1"
EXPECTED_REPORT_STATUS = "PASS_EXACT_42_FRESH_COHORT_ASSERTIONS_PREPARED_NO_ADMISSION_CREDIT"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def verify(config_path: Path, packet_path: Path, report_path: Path) -> dict[str, Any]:
    config = load_object(config_path)
    errors: list[str] = []
    if config.get("protocol_id") != EXPECTED_PROTOCOL_ID:
        errors.append("Unexpected A5 protocol ID")
    root = config_path.resolve().parents[1]
    sources: dict[str, Path] = {}
    for item in config.get("inputs", []):
        path = _resolve(root, item["path"])
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            errors.append(f"Input mismatch: {item['role']}")
        sources[item["role"]] = path
    if Path(config.get("planned_outputs", {}).get("fresh_packet", "")).resolve() != packet_path.resolve():
        errors.append("Fresh packet path differs from protocol")
    if Path(config.get("planned_outputs", {}).get("fresh_report", "")).resolve() != report_path.resolve():
        errors.append("Fresh report path differs from protocol")
    if errors:
        return _result(config_path, packet_path, report_path, 0, 0, errors)

    owner_rows = list(load_object(sources["owner_accepted_records"]).get("records", []))
    ids = [str(row.get("record_id", "")) for row in owner_rows]
    population = config["population_contract"]
    digest = hashlib.sha256(json.dumps(ids, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
    counts = Counter(str(row.get("cohort")) for row in owner_rows)
    if len(ids) != population["record_count"] or len(ids) != len(set(ids)) or digest != population["ordered_record_ids_sha256"]:
        errors.append("Owner population identity mismatch")
    exact = {str(row["record_id"]): row for row in _read_jsonl(sources["exact_text_manifest"])}
    grouping = {str(row["record_id"]): row for row in load_object(sources["post_capture_grouping"])["records"]}
    manual = {str(row["record_id"]): row for row in load_object(sources["manual_group_review"])["records"]}
    packet = _read_jsonl(packet_path)
    if [str(row.get("record_id", "")) for row in packet] != ids:
        errors.append("Fresh packet does not preserve exact owner order")
    expected_keys = {
        "assertion_item_id", "record_id", "cohort", "acquisition_namespace", "availability_plan_id",
        "shortlist_id", "source_text_sha256", "raw_capture_sha256", "opened_overlap_clear",
        "cross_cohort_group_collision", "manual_group_decision", "fresh_cohort", "assertion_status",
        "release_record_materialized", "admission_credit_now",
    }
    checked = 0
    asserted = 0
    namespace = config["fresh_cohort_contract"]["required_acquisition_namespace"]
    required_manual = config["fresh_cohort_contract"]["manual_group_decision_required"]
    for index, row in enumerate(packet, start=1):
        record_id = str(row.get("record_id", ""))
        if set(row) != expected_keys:
            errors.append(f"Unexpected fresh packet fields: {record_id}")
            continue
        source = exact.get(record_id)
        group = grouping.get(record_id)
        review = manual.get(record_id)
        if source is None or group is None or review is None:
            errors.append(f"Missing fresh-cohort source evidence: {record_id}")
            continue
        opened = group.get("opened_overlap")
        independently_clear = isinstance(opened, dict) and bool(opened) and all(not values for values in opened.values())
        expected = {
            "assertion_item_id": f"A5_FRESH_{index:03d}",
            "record_id": record_id,
            "cohort": owner_rows[index - 1].get("cohort"),
            "acquisition_namespace": namespace,
            "availability_plan_id": source.get("availability_plan_id"),
            "shortlist_id": source.get("shortlist_id"),
            "source_text_sha256": source.get("text_sha256"),
            "raw_capture_sha256": source.get("raw_capture_sha256"),
            "opened_overlap_clear": independently_clear,
            "cross_cohort_group_collision": group.get("cross_cohort_group_collision"),
            "manual_group_decision": review.get("group_decision"),
            "fresh_cohort": True,
            "assertion_status": "ASSERTED_FROM_HASH_BOUND_ACQUISITION_AND_EXCLUSION_EVIDENCE",
            "release_record_materialized": False,
            "admission_credit_now": 0,
        }
        if row != expected:
            errors.append(f"Fresh assertion differs from independent recomputation: {record_id}")
        if not record_id.startswith(namespace + "_") or source.get("availability_plan_id") != record_id:
            errors.append(f"Fresh acquisition namespace mismatch: {record_id}")
        if not independently_clear or group.get("cross_cohort_group_collision") is not False or review.get("group_decision") != required_manual:
            errors.append(f"Fresh exclusion evidence did not pass: {record_id}")
        checked += 1
        asserted += row.get("fresh_cohort") is True

    report = load_object(report_path)
    if report.get("status") != EXPECTED_REPORT_STATUS or report.get("protocol_sha256") != sha256_file(config_path) or report.get("packet_sha256") != sha256_file(packet_path):
        errors.append("Fresh report binding mismatch")
    if report.get("population") != {"ordered_record_ids_sha256": digest, "records": len(ids), "development": counts["DEVELOPMENT"], "external_holdout": counts["EXTERNAL_HOLDOUT"]}:
        errors.append("Fresh report population mismatch")
    if report.get("assertion_state") != {"fresh_cohort_asserted": len(ids), "opened_overlap_clear": len(ids), "cross_cohort_collision_free": len(ids), "manual_provisionally_distinct": len(ids)}:
        errors.append("Fresh report assertion-state mismatch")
    decision = report.get("decision", {})
    if decision.get("packet_assertions_ready_for_independent_qa") is not True or decision.get("release_records_materialized") != 0 or decision.get("admission_credit_now") != 0 or decision.get("training_allowed") is not False:
        errors.append("Fresh report opens a forbidden gate")
    return _result(config_path, packet_path, report_path, checked, asserted, errors)


def _result(config_path: Path, packet_path: Path, report_path: Path, checked: int, asserted: int, errors: list[str]) -> dict[str, Any]:
    return {
        "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_A5_FRESH_COHORT_QA_V1",
        "status": "PASS_FRESH_COHORT_PACKET_EXACT_42_FULLY_RECOMPUTED_NO_ADMISSION_CREDIT" if not errors else "FAIL",
        "inputs": {"protocol_sha256": sha256_file(config_path), "packet_sha256": sha256_file(packet_path) if packet_path.is_file() else None, "report_sha256": sha256_file(report_path) if report_path.is_file() else None},
        "checks": {"records_checked": checked, "fresh_cohort_asserted": asserted, "release_records_materialized": 0, "admission_credit_now": 0},
        "decision": {"packet_qa_passed": not errors, "fresh_cohort_evidence_packet_complete": not errors, "channel_contribution_created": False, "training_allowed": False},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "labels_changed": 0, "model_operations": 0, "training_allowed": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite A5 fresh-cohort QA")
    result = verify(args.config, args.packet, args.report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
