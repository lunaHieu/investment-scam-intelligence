"""Prepare a prioritized, non-label human-review plan for the Crimson pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


DEFAULT_DIR = Path(r"D:\nckh 2026-2027\ISI_Data\curated\crimson_external_reference_review_pilot_v1")
DEFAULT_SEC = DEFAULT_DIR / "sec_ai_assisted_first_pass_v1.jsonl"
DEFAULT_IOSCO = DEFAULT_DIR / "iosco_ai_assisted_first_pass_v1.jsonl"
DEFAULT_OUTPUT = DEFAULT_DIR / "human_review_plan_v1.jsonl"

PRIORITY_ORDER = {
    "P0_IMPERSONATION_SUSPECTED": 0,
    "P1_SECOND_REVIEW_WITH_LIVE_GAP": 1,
    "P2_SECOND_REVIEW_LIVE_CONFIRMED": 2,
    "P3_SINGLE_REVIEW_WITH_LIVE_GAP": 3,
    "P4_SINGLE_REVIEW_OFFICIAL_REFERENCE": 4,
}

COMPLETION_FIELDS = [
    "review_status",
    "official_reference_checked",
    "identity_relationship",
    "evidence_assessment",
    "reviewer",
    "reviewed_date",
    "review_notes",
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classify_priority(record: dict[str, Any]) -> str:
    if record.get("identity_relationship") == "IMPERSONATION_SUSPECTED":
        return "P0_IMPERSONATION_SUSPECTED"
    second_review = record.get("second_review_status") == "REQUESTED"
    live_gap = bool(record.get("manual_live_url_followup_required"))
    if second_review and live_gap:
        return "P1_SECOND_REVIEW_WITH_LIVE_GAP"
    if second_review:
        return "P2_SECOND_REVIEW_LIVE_CONFIRMED"
    if live_gap:
        return "P3_SINGLE_REVIEW_WITH_LIVE_GAP"
    return "P4_SINGLE_REVIEW_OFFICIAL_REFERENCE"


def required_action(record: dict[str, Any], priority: str) -> str:
    source = str(record["reference_source"])
    if priority == "P0_IMPERSONATION_SUSPECTED":
        return (
            "Verify the regulator's clone or impersonation wording and the warned host. "
            "Confirm the identity assessment, then complete both human reviews."
        )
    if priority == "P1_SECOND_REVIEW_WITH_LIVE_GAP":
        return (
            "Confirm the available official warning pages, resolve each blocked official URL manually, "
            "then complete two human reviews."
        )
    if priority == "P2_SECOND_REVIEW_LIVE_CONFIRMED":
        return "Confirm every official warning maps to this host, then complete two human reviews."
    if priority == "P3_SINGLE_REVIEW_WITH_LIVE_GAP":
        return (
            "Resolve the blocked official URL manually, confirm the identity and evidence assessment, "
            "then complete one human review."
        )
    if source == "sec_iapd":
        return (
            "Confirm the SEC/IAPD profile lists the same host and entity and verify registration type/status. "
            "Complete one human review; registration is not a safety conclusion."
        )
    return "Confirm the official warning names the host or entity, then complete one human review."


def build_plan_records(
    sec_records: Iterable[dict[str, Any]],
    iosco_records: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    combined = list(sec_records) + list(iosco_records)
    pilot_ids = [str(record.get("pilot_id")) for record in combined]
    if len(set(pilot_ids)) != len(pilot_ids):
        raise ValueError("First-pass pilot IDs must be unique")
    if any(
        record.get("review_status") != "IN_PROGRESS"
        or record.get("training_eligible") != "NO"
        or record.get("label_created") is not False
        for record in combined
    ):
        raise ValueError("Human-review planning accepts only in-progress, non-label records")

    plan: list[dict[str, Any]] = []
    for record in combined:
        source = str(record["reference_source"])
        if source == "iosco_i_scan":
            reference_ids = [str(value) for value in record.get("reference_record_ids", [])]
            urls = [str(detail["official_reference_url"]) for detail in record.get("reference_details", [])]
            live_status = str(record.get("live_reference_status") or "")
        elif source == "sec_iapd":
            reference_ids = [str(record["reference_record_id"])]
            urls = [str(record["official_reference_url"])]
            live_status = "OFFICIAL_PROFILE_SNAPSHOT"
        else:
            raise ValueError(f"Unsupported reference source: {source}")

        priority = classify_priority(record)
        second_review = record.get("second_review_status") == "REQUESTED"
        plan.append(
            {
                "pilot_id": str(record["pilot_id"]),
                "pilot_rank": int(record["pilot_rank"]),
                "review_sheet_row": int(record["pilot_rank"]) + 9,
                "crimson_host": str(record["crimson_host"]),
                "reference_source": source,
                "priority_band": priority,
                "priority_rank": PRIORITY_ORDER[priority],
                "identity_suggestion": str(record["identity_relationship"]),
                "evidence_suggestion": str(record["evidence_assessment"]),
                "live_reference_status": live_status,
                "manual_live_url_followup_required": bool(record.get("manual_live_url_followup_required")),
                "second_review_required": second_review,
                "reference_record_ids": reference_ids,
                "official_reference_urls": urls,
                "required_action": required_action(record, priority),
                "required_completion_fields": COMPLETION_FIELDS + (["second_reviewer"] if second_review else []),
                "do_not_open_crimson_host": True,
                "human_confirmation_required": True,
                "review_status": "IN_PROGRESS",
                "adjudication_status": "NOT_READY",
                "training_eligible": "NO",
                "label_created": False,
            }
        )

    plan.sort(key=lambda row: (int(row["priority_rank"]), int(row["pilot_rank"])))
    for review_order, row in enumerate(plan, start=1):
        row["review_order"] = review_order
    return plan


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing human-review plan: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in records)
    path.write_text(payload, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sec-first-pass", type=Path, default=DEFAULT_SEC)
    parser.add_argument("--iosco-first-pass", type=Path, default=DEFAULT_IOSCO)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    sec = load_jsonl(args.sec_first_pass)
    iosco = load_jsonl(args.iosco_first_pass)
    if len(sec) != 8 or len(iosco) != 32:
        raise ValueError(f"Expected 8 SEC and 32 IOSCO records, received {len(sec)} and {len(iosco)}")
    plan = build_plan_records(sec, iosco)
    write_jsonl(args.output, plan)
    print(json.dumps({
        "output": str(args.output),
        "record_count": len(plan),
        "sha256": sha256_file(args.output),
        "priority_counts": dict(Counter(row["priority_band"] for row in plan)),
        "second_review_required_count": sum(bool(row["second_review_required"]) for row in plan),
        "manual_live_url_followup_count": sum(bool(row["manual_live_url_followup_required"]) for row in plan),
        "training_eligible_count": 0,
        "labels_created": 0,
    }, indent=2))


if __name__ == "__main__":
    main()
