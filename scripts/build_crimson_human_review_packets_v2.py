"""Build deterministic offline human-review task packets for Crimson."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_RELEASE_ID = "ISI_CRIMSON_HUMAN_REVIEW_PACKETS_V2"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"Expected object at {path}:{number}")
        rows.append(value)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    content = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    path.write_text(content, encoding="utf-8")


def resolve(repo_root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else repo_root / path


def _blank_human_fields() -> dict[str, Any]:
    return {
        "review_status": "NOT_STARTED",
        "official_reference_checked": "",
        "identity_relationship": "",
        "evidence_assessment": "",
        "reviewer": "",
        "reviewed_date": "",
        "review_notes": "",
        "training_eligible": "NO",
        "label_created": False,
    }


def _blind_second_task(row: dict[str, Any], dependency_status: str) -> dict[str, Any]:
    task = {
        "task_id": f"CRIMSON_SECOND_{row['pilot_id']}",
        "task_type": "BLIND_HUMAN_SECOND_REVIEW",
        "dependency_status": dependency_status,
        "pilot_id": row["pilot_id"],
        "pilot_rank": row["pilot_rank"],
        "crimson_host": row["crimson_host"],
        "do_not_open_crimson_host": True,
        "reference_source": row["reference_source"],
        "reference_record_ids": row["reference_record_ids"],
        "official_reference_urls": row["official_reference_urls"],
        "allowed_identity_relationships": [
            "SAME_ENTITY",
            "IMPERSONATION_SUSPECTED",
            "UNRELATED",
            "UNCLEAR",
        ],
        "allowed_evidence_assessments": [
            "WARNING_RELEVANT",
            "REGISTRATION_RELEVANT",
            "REFERENCE_NOT_APPLICABLE",
            "INSUFFICIENT_EVIDENCE",
        ],
        "blind_fields_omitted": [
            "identity_suggestion",
            "evidence_suggestion",
            "first_reviewer",
            "first_review_decision",
            "first_review_notes",
        ],
    }
    task.update(_blank_human_fields())
    return task


def build_packets(config_path: Path) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    config = load_object(config_path)
    if config.get("release_id") != EXPECTED_RELEASE_ID:
        raise ValueError("Unexpected Crimson packet release ID")
    contract = config["packet_contract"]
    if contract["human_decisions_created"] or contract["labels_created"]:
        raise ValueError("Release permits decisions or labels")
    if contract["crimson_domain_access_allowed"] or config["decision"]["network_execution_allowed"]:
        raise ValueError("Release permits domain or network access")
    if contract["output_overwrite_allowed"]:
        raise ValueError("Release permits output overwrite")

    repo_root = config_path.resolve().parents[1]
    for item in config["inputs"].values():
        path = resolve(repo_root, item["path"])
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise ValueError(f"Input missing or changed: {item['path']}")

    plan = load_jsonl(resolve(repo_root, config["inputs"]["review_plan"]["path"]))
    decisions = load_jsonl(resolve(repo_root, config["inputs"]["review_decisions"]["path"]))
    if len(plan) != 40 or len(decisions) != 1:
        raise ValueError("Unexpected plan or decision population")
    plan_by_id = {row["pilot_id"]: row for row in plan}
    decisions_by_id = {row["pilot_id"]: row for row in decisions}
    if len(plan_by_id) != 40 or len(decisions_by_id) != 1:
        raise ValueError("Duplicate plan or decision pilot ID")
    if not set(decisions_by_id).issubset(plan_by_id):
        raise ValueError("Decision references an unknown pilot ID")

    first_pending: list[dict[str, Any]] = []
    second_ready: list[dict[str, Any]] = []
    second_waiting: list[dict[str, Any]] = []
    live_followup: list[dict[str, Any]] = []
    for row in sorted(plan, key=lambda item: item["review_order"]):
        pilot_id = row["pilot_id"]
        decision = decisions_by_id.get(pilot_id)
        first_complete = bool(decision and decision.get("review_status") == "COMPLETED")
        if not first_complete:
            task = dict(row)
            task["task_id"] = f"CRIMSON_FIRST_{pilot_id}"
            task["task_type"] = "HUMAN_FIRST_REVIEW"
            task["review_status"] = "NOT_STARTED"
            first_pending.append(task)
        if row.get("second_review_required") is True:
            task = _blind_second_task(
                row,
                "READY_FIRST_REVIEW_COMPLETE" if first_complete else "WAITING_FIRST_REVIEW",
            )
            (second_ready if first_complete else second_waiting).append(task)
        live_resolved_by_decision = bool(
            decision and decision.get("live_reference_status") == "ALL_URLS_LIVE_CONFIRMED"
        )
        if row.get("manual_live_url_followup_required") is True and not live_resolved_by_decision:
            live_followup.append(
                {
                    "task_id": f"CRIMSON_REFERENCE_{pilot_id}",
                    "task_type": "OFFICIAL_REFERENCE_MANUAL_FOLLOWUP",
                    "pilot_id": pilot_id,
                    "pilot_rank": row["pilot_rank"],
                    "crimson_host": row["crimson_host"],
                    "do_not_open_crimson_host": True,
                    "reference_source": row["reference_source"],
                    "reference_record_ids": row["reference_record_ids"],
                    "official_reference_urls": row["official_reference_urls"],
                    "followup_status": "PENDING_HUMAN_OFFICIAL_REFERENCE_CHECK",
                    "network_automation_allowed": False,
                    "training_eligible": "NO",
                    "label_created": False,
                }
            )

    packets = {
        "first_review_pending": first_pending,
        "blind_second_review_ready": second_ready,
        "blind_second_review_waiting": second_waiting,
        "official_reference_followup": live_followup,
    }
    expected_counts = {
        "first_review_pending": contract["expected_first_review_pending"],
        "blind_second_review_ready": contract["expected_blind_second_review_ready"],
        "blind_second_review_waiting": contract["expected_blind_second_review_waiting"],
        "official_reference_followup": contract["expected_official_reference_followup"],
    }
    actual_counts = {key: len(value) for key, value in packets.items()}
    if actual_counts != expected_counts:
        raise ValueError(f"Packet counts changed: {actual_counts}")
    if len(second_ready) + len(second_waiting) != contract["expected_second_review_population"]:
        raise ValueError("Second-review population changed")
    task_ids = [row["task_id"] for rows in packets.values() for row in rows]
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("Task IDs are not unique across outputs")
    forbidden_blind = {
        "identity_suggestion",
        "evidence_suggestion",
        "first_reviewer",
        "first_review_decision",
        "first_review_notes",
    }
    for row in second_ready + second_waiting:
        if forbidden_blind.intersection(row):
            raise ValueError("Blind second-review packet leaked a prior suggestion or decision")

    report = {
        "report_id": "ISI_CRIMSON_HUMAN_REVIEW_PACKET_REPORT_V2",
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "status": "PASS_PACKETS_READY_NO_DECISIONS_CREATED",
        "release": {"path": str(config_path.resolve()), "sha256": sha256_file(config_path)},
        "counts": actual_counts,
        "second_review_population": len(second_ready) + len(second_waiting),
        "completed_first_review_count": len(decisions),
        "live_gap_recomputed_from_current_decisions": len(live_followup),
        "human_decisions_created": 0,
        "labels_created": 0,
        "training_eligible_records": 0,
        "network_operations": 0,
    }
    return packets, report


def materialize(config_path: Path, output_root: Path | None = None) -> dict[str, Any]:
    config = load_object(config_path)
    packets, report = build_packets(config_path)
    root = output_root or Path(config["planned_outputs"]["root"])
    names = config["planned_outputs"]
    targets = {key: root / names[key] for key in packets}
    report_path = root / names["report"]
    if any(path.exists() for path in [*targets.values(), report_path]):
        raise FileExistsError(f"Refusing to overwrite Crimson packet output under {root}")
    root.mkdir(parents=True, exist_ok=True)
    for key, rows in packets.items():
        write_jsonl(targets[key], rows)
    report["outputs"] = {
        key: {
            "path": str(targets[key].resolve()),
            "sha256": sha256_file(targets[key]),
            "record_count": len(packets[key]),
        }
        for key in packets
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()
    print(json.dumps(materialize(args.config, args.output_root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
