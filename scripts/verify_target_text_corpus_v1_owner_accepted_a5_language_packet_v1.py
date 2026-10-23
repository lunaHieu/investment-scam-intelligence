"""Independently verify the exact-42 A5 language-review packet."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


EXPECTED_PROTOCOL_ID = "ISI_TARGET_TEXT_CORPUS_V1_OWNER_ACCEPTED_A5_PACKET_PROTOCOL_V1"
EXPECTED_REPORT_STATUS = "PASS_EXACT_42_LANGUAGE_REVIEW_PACKET_PREPARED_HUMAN_DECISIONS_PENDING"


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
    if Path(config.get("planned_outputs", {}).get("language_packet", "")).resolve() != packet_path.resolve():
        errors.append("Language packet path differs from protocol")
    if Path(config.get("planned_outputs", {}).get("language_report", "")).resolve() != report_path.resolve():
        errors.append("Language report path differs from protocol")
    if errors:
        return _result(config_path, packet_path, report_path, 0, 0, 0, errors)

    owner_rows = list(load_object(sources["owner_accepted_records"]).get("records", []))
    ids = [str(row.get("record_id", "")) for row in owner_rows]
    population = config["population_contract"]
    digest = hashlib.sha256(json.dumps(ids, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
    counts = Counter(str(row.get("cohort")) for row in owner_rows)
    if len(ids) != population["record_count"] or len(ids) != len(set(ids)) or digest != population["ordered_record_ids_sha256"]:
        errors.append("Owner population identity mismatch")
    if counts != {"DEVELOPMENT": population["development_count"], "EXTERNAL_HOLDOUT": population["external_holdout_count"]}:
        errors.append("Owner cohort counts mismatch")
    exact = {str(row["record_id"]): row for row in _read_jsonl(sources["exact_text_manifest"])}
    packet = _read_jsonl(packet_path)
    if [str(row.get("record_id", "")) for row in packet] != ids:
        errors.append("Language packet does not preserve exact owner order")
    expected_keys = {
        "review_item_id", "record_id", "cohort", "source_text_path", "source_text_sha256",
        "non_whitespace_text_characters", "automatic_language_hint", "language_code",
        "human_reviewed_language", "review_status", "ground_truth_status_changed", "admission_credit_now",
    }
    checked = 0
    pending = 0
    for index, row in enumerate(packet, start=1):
        record_id = str(row.get("record_id", ""))
        if set(row) != expected_keys:
            errors.append(f"Unexpected language packet fields: {record_id}")
            continue
        source = exact.get(record_id)
        if source is None:
            errors.append(f"Missing source text manifest row: {record_id}")
            continue
        text_path = Path(str(row.get("source_text_path", "")))
        if not text_path.is_file() or sha256_file(text_path) != row.get("source_text_sha256") or row.get("source_text_sha256") != source.get("text_sha256"):
            errors.append(f"Visible-text hash chain mismatch: {record_id}")
        if row.get("review_item_id") != f"A5_LANGUAGE_{index:03d}" or row.get("cohort") != owner_rows[index - 1].get("cohort"):
            errors.append(f"Language packet identity mismatch: {record_id}")
        if row.get("non_whitespace_text_characters") != source.get("non_whitespace_text_characters"):
            errors.append(f"Language packet text count mismatch: {record_id}")
        if row.get("automatic_language_hint") is not None or row.get("language_code") is not None or row.get("human_reviewed_language") is not False:
            errors.append(f"Language decision was prefilled or fabricated: {record_id}")
        if row.get("review_status") != config["language_review_contract"]["initial_review_status"]:
            errors.append(f"Language review status is not pending: {record_id}")
        if row.get("ground_truth_status_changed") is not False or row.get("admission_credit_now") != 0:
            errors.append(f"Language packet changes label or admission state: {record_id}")
        checked += 1
        pending += row.get("review_status") == config["language_review_contract"]["initial_review_status"]

    report = load_object(report_path)
    packet_hash = sha256_file(packet_path)
    if report.get("status") != EXPECTED_REPORT_STATUS or report.get("protocol_sha256") != sha256_file(config_path) or report.get("packet_sha256") != packet_hash:
        errors.append("Language report binding mismatch")
    if report.get("population") != {"ordered_record_ids_sha256": digest, "records": len(ids), "development": counts["DEVELOPMENT"], "external_holdout": counts["EXTERNAL_HOLDOUT"]}:
        errors.append("Language report population mismatch")
    if report.get("review_state") != {"pending_human_review": len(ids), "completed_human_review": 0, "language_codes_materialized": 0, "automatic_hints_used_as_final": 0}:
        errors.append("Language report review-state mismatch")
    decision = report.get("decision", {})
    if decision.get("human_review_still_required") is not True or decision.get("admission_credit_now") != 0 or decision.get("candidate_manifest_created") is not False or decision.get("training_allowed") is not False:
        errors.append("Language report opens a forbidden gate")
    return _result(config_path, packet_path, report_path, checked, pending, counts["DEVELOPMENT"], errors)


def _result(config_path: Path, packet_path: Path, report_path: Path, checked: int, pending: int, development: int, errors: list[str]) -> dict[str, Any]:
    return {
        "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_A5_LANGUAGE_PACKET_QA_V1",
        "status": "PASS_LANGUAGE_PACKET_EXACT_42_HASH_RECOMPUTED_HUMAN_REVIEW_PENDING" if not errors else "FAIL",
        "inputs": {"protocol_sha256": sha256_file(config_path), "packet_sha256": sha256_file(packet_path) if packet_path.is_file() else None, "report_sha256": sha256_file(report_path) if report_path.is_file() else None},
        "checks": {"records_checked": checked, "pending_human_review": pending, "development_records": development, "language_codes_materialized": 0},
        "decision": {"packet_qa_passed": not errors, "human_review_complete": False, "admission_credit_now": 0, "training_allowed": False},
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
        raise FileExistsError("Refusing to overwrite A5 language QA")
    result = verify(args.config, args.packet, args.report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
