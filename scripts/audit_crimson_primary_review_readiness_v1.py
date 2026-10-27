"""Independently audit readiness of the 39 pending Crimson primary-review tasks."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse


PASS_STATUS = "PASS_39_PRIMARY_TASKS_INTEGRITY_VERIFIED_24_READY_15_FOLLOWUP_REQUIRED"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _input(config: dict, role: str) -> Path:
    item = next(item for item in config["inputs"] if item["role"] == role)
    path = Path(item["path"])
    if not path.is_file() or sha256_file(path) != item["sha256"]:
        raise ValueError(f"Input hash mismatch: {role}")
    return path


def audit(config_path: Path) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if config.get("audit_id") != "ISI_CRIMSON_PRIMARY_REVIEW_READINESS_AUDIT_V1":
        errors.append("Unexpected audit identity")
    try:
        pending = read_jsonl(_input(config, "first_review_pending"))
        followup = read_jsonl(_input(config, "official_reference_followup"))
        first_pass = read_jsonl(_input(config, "sec_ai_first_pass")) + read_jsonl(_input(config, "iosco_ai_first_pass"))
    except Exception as exc:
        return {"status": "FAIL", "errors": [f"Input validation failed: {type(exc).__name__}: {exc}"]}

    expected = config["expected"]
    if len(pending) != expected["pending_tasks"]:
        errors.append("Pending task count changed")
    if len(followup) != expected["official_followup_tasks"]:
        errors.append("Official follow-up task count changed")
    if len(first_pass) != expected["ai_first_pass_records"]:
        errors.append("AI first-pass population changed")

    for key in ("task_id", "pilot_id", "crimson_host", "review_order"):
        values = [row.get(key) for row in pending]
        if len(values) != len(set(values)):
            errors.append(f"Pending task field is not unique: {key}")
    if [row.get("review_order") for row in pending] != list(range(2, 41)):
        errors.append("Pending review order is not the frozen 2..40 sequence")

    base_fields = [
        "review_status", "official_reference_checked", "identity_relationship",
        "evidence_assessment", "reviewer", "reviewed_date", "review_notes",
    ]
    first_pass_by_pilot = {row["pilot_id"]: row for row in first_pass}
    followup_by_pilot = {row["pilot_id"]: row for row in followup}
    records: list[dict] = []
    for row in pending:
        pilot_id = row.get("pilot_id")
        required = list(row.get("required_completion_fields", []))
        expected_required = base_fields + (["second_reviewer"] if row.get("second_review_required") else [])
        if required != expected_required:
            errors.append(f"Required completion fields changed: {pilot_id}")
        fixed = {
            "task_type": "HUMAN_FIRST_REVIEW",
            "review_status": "NOT_STARTED",
            "adjudication_status": "NOT_READY",
            "do_not_open_crimson_host": True,
            "human_confirmation_required": True,
            "label_created": False,
            "training_eligible": "NO",
        }
        for key, value in fixed.items():
            if row.get(key) != value:
                errors.append(f"Safety field changed for {pilot_id}: {key}")

        urls = row.get("official_reference_urls", [])
        if not urls:
            errors.append(f"Official reference URL missing: {pilot_id}")
        for url in urls:
            parsed = urlparse(url)
            if parsed.scheme != "https" or not parsed.hostname:
                errors.append(f"Official reference URL is not HTTPS: {pilot_id}")
            if parsed.hostname and parsed.hostname.lower().removeprefix("www.") == str(row.get("crimson_host", "")).lower().removeprefix("www."):
                errors.append(f"Official URL resolves to forbidden Crimson host: {pilot_id}")

        source = first_pass_by_pilot.get(pilot_id)
        if source is None:
            errors.append(f"AI first-pass evidence missing: {pilot_id}")
        else:
            pairs = (
                ("crimson_host", "crimson_host"),
                ("reference_source", "reference_source"),
                ("identity_suggestion", "identity_relationship"),
                ("evidence_suggestion", "evidence_assessment"),
            )
            for packet_key, source_key in pairs:
                if row.get(packet_key) != source.get(source_key):
                    errors.append(f"First-pass mismatch for {pilot_id}: {packet_key}")

        needs_followup = bool(row.get("manual_live_url_followup_required"))
        followup_row = followup_by_pilot.get(pilot_id)
        if needs_followup != (followup_row is not None):
            errors.append(f"Official follow-up membership mismatch: {pilot_id}")
        if followup_row is not None:
            for key in ("crimson_host", "reference_source", "reference_record_ids", "official_reference_urls"):
                if row.get(key) != followup_row.get(key):
                    errors.append(f"Official follow-up content mismatch for {pilot_id}: {key}")

        records.append({
            "task_id": row.get("task_id"),
            "pilot_id": pilot_id,
            "priority_band": row.get("priority_band"),
            "reference_source": row.get("reference_source"),
            "second_review_required": bool(row.get("second_review_required")),
            "readiness": "OFFICIAL_REFERENCE_FOLLOWUP_REQUIRED" if needs_followup else "READY_FOR_TRUTHFUL_HUMAN_PRIMARY_REVIEW",
            "human_confirmation_required": True,
            "label_created": False,
            "training_eligible": "NO",
        })

    ready = sum(record["readiness"] == "READY_FOR_TRUTHFUL_HUMAN_PRIMARY_REVIEW" for record in records)
    followup_count = len(records) - ready
    second = sum(record["second_review_required"] for record in records)
    if ready != expected["ready_without_followup"] or followup_count != expected["followup_required"] or second != expected["second_review_required"]:
        errors.append("Readiness counts changed")

    return {
        "report_id": "ISI_CRIMSON_PRIMARY_REVIEW_READINESS_REPORT_V1",
        "created_at": config["audit_snapshot_at"],
        "status": PASS_STATUS if not errors else "FAIL",
        "config": {"path": str(config_path.resolve()), "sha256": sha256_file(config_path)},
        "counts": {
            "pending_primary_tasks": len(pending),
            "ready_for_truthful_human_primary_review": ready,
            "official_reference_followup_required": followup_count,
            "second_review_required_after_primary": second,
            "single_review_tasks": len(pending) - second,
            "ai_first_pass_records": len(first_pass),
            "human_decisions_created": 0,
            "labels_created": 0,
            "training_eligible_records": 0,
        },
        "records": records,
        "decision": {
            "packet_integrity_verified": not errors,
            "ready_tasks_may_be_assigned_to_truthful_human_reviewer": not errors,
            "followup_tasks_require_official_reference_check": True,
            "ai_may_impersonate_human_reviewer": False,
            "crimson_host_access_allowed": False,
            "automatic_labeling_allowed": False,
            "training_allowed": False,
        },
        "errors": errors,
        "safety_contract": {
            "network_operations": 0,
            "crimson_host_access_operations": 0,
            "human_decisions_created": 0,
            "labels_created": 0,
            "model_operations": 0,
            "training_allowed": False,
        },
    }


def write_report(config_path: Path, output_path: Path) -> dict:
    partial = output_path.with_suffix(output_path.suffix + ".partial")
    if output_path.exists() or partial.exists():
        raise FileExistsError("Refusing to overwrite Crimson readiness report")
    result = audit(config_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(output_path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    output = args.output or Path(config["planned_output"]["report_path"])
    result = write_report(args.config, output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
