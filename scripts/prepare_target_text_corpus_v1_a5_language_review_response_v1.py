"""Prepare the hash-bound exact-42 A5 language-review response template."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


EXPECTED_PROTOCOL_ID = "ISI_TARGET_TEXT_CORPUS_V1_A5_LANGUAGE_REVIEW_RESPONSE_PROTOCOL_V1"
EXPECTED_PACKET_QA_STATUS = "PASS_LANGUAGE_PACKET_EXACT_42_HASH_RECOMPUTED_HUMAN_REVIEW_PENDING"


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _ordered_ids_sha256(rows: list[dict[str, Any]]) -> str:
    ids = [str(row["record_id"]) for row in rows]
    return hashlib.sha256(json.dumps(ids, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def prepare(config_path: Path) -> dict[str, Any]:
    config = load_object(config_path)
    if config.get("protocol_id") != EXPECTED_PROTOCOL_ID:
        raise ValueError("Unexpected C3 language-response protocol ID")
    root = config_path.resolve().parents[1]
    inputs: dict[str, Path] = {}
    for item in config.get("inputs", []):
        path = _resolve(root, str(item["path"]))
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            raise ValueError(f"Missing or changed C3 input: {item.get('role')}")
        inputs[str(item["role"])] = path

    packet_qa = load_object(inputs["language_packet_independent_qa"])
    if packet_qa.get("status") != EXPECTED_PACKET_QA_STATUS or packet_qa.get("errors") != []:
        raise ValueError("A5 language packet independent QA is not clean")
    packet = _read_jsonl(inputs["language_packet"])
    population = config["population_contract"]
    counts = Counter(str(row.get("cohort")) for row in packet)
    if len(packet) != population["record_count"] or len({str(row.get("record_id")) for row in packet}) != len(packet):
        raise ValueError("A5 language packet population is not exact and unique")
    if counts != Counter({"DEVELOPMENT": population["development_count"], "EXTERNAL_HOLDOUT": population["external_holdout_count"]}):
        raise ValueError("A5 language packet cohort counts changed")
    if _ordered_ids_sha256(packet) != population["ordered_record_ids_sha256"]:
        raise ValueError("A5 language packet order changed")

    template_rows: list[dict[str, Any]] = []
    for row in packet:
        text_path = Path(str(row.get("source_text_path", "")))
        if not text_path.is_file() or sha256_file(text_path) != row.get("source_text_sha256"):
            raise ValueError(f"Visible-text hash mismatch: {row.get('record_id')}")
        if row.get("human_reviewed_language") is not False or row.get("language_code") is not None:
            raise ValueError(f"A5 packet contains a prefilled language decision: {row.get('record_id')}")
        template_rows.append(
            {
                "review_item_id": row["review_item_id"],
                "record_id": row["record_id"],
                "cohort": row["cohort"],
                "source_text_path": row["source_text_path"],
                "source_text_sha256": row["source_text_sha256"],
                "non_whitespace_text_characters": row["non_whitespace_text_characters"],
                "language_code": None,
                "human_reviewed_language": False,
                "review_status": "PENDING_HUMAN_LANGUAGE_REVIEW",
                "reviewed_at": None,
                "rationale": None,
            }
        )

    template = {
        "response_id": "REPLACE_WITH_UNIQUE_HUMAN_RESPONSE_ID",
        "protocol_id": EXPECTED_PROTOCOL_ID,
        "status": "TEMPLATE_NOT_A_COMPLETED_RESPONSE",
        "created_at": None,
        "language_packet_sha256": population["language_packet_sha256"],
        "ordered_record_ids_sha256": population["ordered_record_ids_sha256"],
        "reviewer": {
            "reviewer_id": None,
            "reviewer_type": None,
            "independent_human_attestation": False,
            "hash_verified_visible_text_attestation": False,
            "automatic_or_ai_hint_used_as_final": None,
        },
        "records": template_rows,
    }
    return {"config": config, "template": template, "counts": counts}


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _write_no_overwrite(path: Path, payload: bytes) -> None:
    partial = path.with_suffix(path.suffix + ".partial")
    if path.exists() or partial.exists():
        raise FileExistsError(f"Refusing to overwrite C3 output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    partial.write_bytes(payload)
    partial.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.config)
    outputs = result["config"]["planned_outputs"]
    template_path = Path(outputs["response_template"])
    report_path = Path(outputs["preparation_report"])
    for key in ("completed_response", "independent_response_qa", "language_supply_report"):
        path = Path(outputs[key])
        if path.exists() or path.with_suffix(path.suffix + ".partial").exists():
            raise FileExistsError(f"Future human-response output already exists: {path}")
    template_bytes = _json_bytes(result["template"])
    report = {
        "report_id": "ISI_TARGET_TEXT_CORPUS_V1_A5_LANGUAGE_RESPONSE_PREPARATION_REPORT_V1",
        "status": "PASS_C3_TEMPLATE_PREPARED_HUMAN_RESPONSE_ABSENT",
        "protocol_sha256": sha256_file(args.config),
        "template_sha256": hashlib.sha256(template_bytes).hexdigest(),
        "population": {
            "records": len(result["template"]["records"]),
            "development": result["counts"]["DEVELOPMENT"],
            "external_holdout": result["counts"]["EXTERNAL_HOLDOUT"],
        },
        "review_state": {"pending_human_review": len(result["template"]["records"]), "completed_human_review": 0},
        "decision": {"tooling_ready": True, "human_response_exists": False, "language_supply_credit_now": 0, "training_allowed": False},
        "safety_contract": {"network_operations": 0, "human_decisions_fabricated": 0, "labels_changed": 0, "model_operations": 0},
    }
    _write_no_overwrite(template_path, template_bytes)
    _write_no_overwrite(report_path, _json_bytes(report))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
