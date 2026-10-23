"""Verify one completed human response for the exact-42 A5 language packet."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.prepare_target_text_corpus_v1_a5_language_review_response_v1 import _read_jsonl, _resolve
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


EXPECTED_PROTOCOL_ID = "ISI_TARGET_TEXT_CORPUS_V1_A5_LANGUAGE_REVIEW_RESPONSE_PROTOCOL_V1"
TOP_LEVEL_FIELDS = {"response_id", "protocol_id", "status", "created_at", "language_packet_sha256", "ordered_record_ids_sha256", "reviewer", "records"}
REVIEWER_FIELDS = {"reviewer_id", "reviewer_type", "independent_human_attestation", "hash_verified_visible_text_attestation", "automatic_or_ai_hint_used_as_final"}
RECORD_FIELDS = {"review_item_id", "record_id", "cohort", "source_text_path", "source_text_sha256", "non_whitespace_text_characters", "language_code", "human_reviewed_language", "review_status", "reviewed_at", "rationale"}


def _valid_datetime(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def verify(config_path: Path, response_path: Path) -> dict[str, Any]:
    config = load_object(config_path)
    errors: list[str] = []
    if config.get("protocol_id") != EXPECTED_PROTOCOL_ID:
        errors.append("Unexpected C3 protocol ID")
    root = config_path.resolve().parents[1]
    inputs: dict[str, Path] = {}
    for item in config.get("inputs", []):
        path = _resolve(root, str(item["path"]))
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            errors.append(f"Input mismatch: {item.get('role')}")
        inputs[str(item["role"])] = path
    if errors:
        return _result(config_path, response_path, {}, Counter(), 0, errors)

    response = load_object(response_path)
    contract = config["human_review_contract"]
    population = config["population_contract"]
    if set(response) != TOP_LEVEL_FIELDS:
        errors.append("Completed response top-level fields differ from schema")
    if response.get("protocol_id") != EXPECTED_PROTOCOL_ID or response.get("status") != contract["response_status_required"]:
        errors.append("Completed response is not bound to the frozen protocol/status")
    if not isinstance(response.get("response_id"), str) or not response.get("response_id") or not _valid_datetime(response.get("created_at")):
        errors.append("Completed response identity or timezone-aware created_at is invalid")
    if response.get("language_packet_sha256") != population["language_packet_sha256"] or response.get("ordered_record_ids_sha256") != population["ordered_record_ids_sha256"]:
        errors.append("Completed response population binding changed")
    reviewer = response.get("reviewer")
    if not isinstance(reviewer, dict) or set(reviewer) != REVIEWER_FIELDS:
        errors.append("Reviewer attestation fields differ from schema")
    else:
        if not isinstance(reviewer.get("reviewer_id"), str) or not reviewer.get("reviewer_id"):
            errors.append("Human reviewer ID is missing")
        if reviewer.get("reviewer_type") != "HUMAN" or reviewer.get("independent_human_attestation") is not True:
            errors.append("Truthful independent human attestation is missing")
        if reviewer.get("hash_verified_visible_text_attestation") is not True:
            errors.append("Hash-verified visible-text attestation is missing")
        if reviewer.get("automatic_or_ai_hint_used_as_final") is not False:
            errors.append("Automatic or AI hint was used as final language evidence")

    packet = _read_jsonl(inputs["language_packet"])
    records = response.get("records")
    if not isinstance(records, list) or len(records) != population["record_count"]:
        errors.append("Completed response does not cover exactly 42 records")
        records = records if isinstance(records, list) else []
    codes: Counter[str] = Counter()
    verified = 0
    pattern = re.compile(contract["language_code_pattern"])
    if [str(row.get("record_id", "")) for row in records] != [str(row["record_id"]) for row in packet]:
        errors.append("Completed response does not preserve exact packet order")
    for index, expected in enumerate(packet):
        if index >= len(records):
            break
        row = records[index]
        record_id = str(expected["record_id"])
        if not isinstance(row, dict) or set(row) != RECORD_FIELDS:
            errors.append(f"Response fields differ from schema: {record_id}")
            continue
        for field in ("review_item_id", "record_id", "cohort", "source_text_path", "source_text_sha256", "non_whitespace_text_characters"):
            if row.get(field) != expected.get(field):
                errors.append(f"Hash-bound field changed for {record_id}: {field}")
        text_path = Path(str(expected["source_text_path"]))
        if not text_path.is_file() or sha256_file(text_path) != expected["source_text_sha256"]:
            errors.append(f"Visible-text bytes changed: {record_id}")
        language_code = row.get("language_code")
        if not isinstance(language_code, str) or pattern.fullmatch(language_code) is None:
            errors.append(f"Invalid lowercase language code: {record_id}")
        else:
            codes[language_code] += 1
        if row.get("human_reviewed_language") is not True or row.get("review_status") != "COMPLETED_HUMAN_LANGUAGE_REVIEW":
            errors.append(f"Human language decision is incomplete: {record_id}")
        if not _valid_datetime(row.get("reviewed_at")):
            errors.append(f"Review timestamp is invalid: {record_id}")
        if not isinstance(row.get("rationale"), str) or not row.get("rationale").strip():
            errors.append(f"Review rationale is missing: {record_id}")
        verified += 1
    return _result(config_path, response_path, response, codes, verified, errors)


def _result(config_path: Path, response_path: Path, response: dict[str, Any], codes: Counter[str], verified: int, errors: list[str]) -> dict[str, Any]:
    vietnamese = sum(count for code, count in codes.items() if code == "vi" or code.startswith("vi-"))
    return {
        "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_A5_LANGUAGE_RESPONSE_QA_V1",
        "status": "PASS_EXACT_42_HUMAN_LANGUAGE_RESPONSE_HASH_RECOMPUTED" if not errors else "FAIL",
        "inputs": {
            "protocol_sha256": sha256_file(config_path),
            "response_sha256": sha256_file(response_path) if response_path.is_file() else None,
            "response_id": response.get("response_id"),
        },
        "checks": {"records_verified": verified, "language_counts": dict(sorted(codes.items())), "vietnamese_records": vietnamese},
        "decision": {
            "human_language_review_verified": not errors,
            "language_supply_may_be_recomputed": not errors,
            "labels_changed": 0,
            "v1_core_admission_credit_now": 0,
            "training_allowed": False,
        },
        "errors": errors,
        "safety_contract": {"network_operations": 0, "labels_changed": 0, "model_operations": 0, "training_allowed": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--response", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite C3 response QA")
    result = verify(args.config, args.response)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
