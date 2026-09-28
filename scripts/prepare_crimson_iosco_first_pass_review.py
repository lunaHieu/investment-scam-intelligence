"""Prepare an evidence-backed, non-label IOSCO first pass for the Crimson pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PILOT = Path(r"D:\nckh 2026-2027\ISI_Data\curated\crimson_external_reference_review_pilot_v1\pilot_records_v1.jsonl")
DEFAULT_EVIDENCE = Path(r"D:\nckh 2026-2027\ISI_Data\curated\crimson_external_reference_review_pilot_v1\evidence_records_v1.jsonl")
DEFAULT_IOSCO_INDEX = Path(r"D:\nckh 2026-2027\ISI_Data\derived\external_reference_indices_v1\iosco_warning_reference_v1.jsonl")
DEFAULT_LIVE_CHECKS = ROOT / "configs" / "crimson_iosco_live_reference_check_v1.json"
DEFAULT_OUTPUT = Path(r"D:\nckh 2026-2027\ISI_Data\curated\crimson_external_reference_review_pilot_v1\iosco_ai_assisted_first_pass_v1.jsonl")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def host_is_same_or_subdomain(candidate: str, reference: str) -> bool:
    candidate = candidate.lower().strip(".")
    reference = reference.lower().strip(".")
    return candidate == reference or candidate.endswith(f".{reference}")


def identity_suggestion(reference_records: Iterable[dict[str, Any]]) -> str:
    tokens: list[str] = []
    for record in reference_records:
        tokens.extend(str(value).lower() for value in record.get("entity_name_keys", []))
        tokens.append(str((record.get("warning_categories") or {}).get("detail") or "").lower())
    joined = " ".join(tokens)
    if any(marker in joined for marker in (" clone", "imposter", "impersonator")):
        return "IMPERSONATION_SUSPECTED"
    return "SAME_ENTITY"


def aggregate_live_status(statuses: Iterable[str]) -> str:
    values = list(statuses)
    confirmed = sum(value == "LIVE_CONFIRMED" for value in values)
    if confirmed == len(values):
        return "ALL_URLS_LIVE_CONFIRMED"
    if confirmed:
        return "PARTIAL_URLS_LIVE_CONFIRMED"
    return "SNAPSHOT_ONLY_LIVE_NOT_CONFIRMED"


def prepare_records(
    pilot_records: Iterable[dict[str, Any]],
    evidence_records: Iterable[dict[str, Any]],
    iosco_records: Iterable[dict[str, Any]],
    live_check: dict[str, Any],
) -> list[dict[str, Any]]:
    iosco_pilot = [row for row in pilot_records if row.get("reference_sources") == ["iosco_i_scan"]]
    if len(iosco_pilot) != 32:
        raise ValueError(f"Expected 32 IOSCO pilot rows, received {len(iosco_pilot)}")

    evidence_by_pilot: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in evidence_records:
        if row.get("match_source_id") == "iosco_i_scan":
            evidence_by_pilot[str(row["pilot_id"])].append(row)
    iosco_by_id = {str(row["source_record_id"]): row for row in iosco_records}
    live_by_url = {str(row["url"]): row for row in live_check.get("records", [])}
    evidence_urls = {
        str(row["notice_reference_url"])
        for rows in evidence_by_pilot.values()
        for row in rows
    }
    if evidence_urls != set(live_by_url):
        missing = sorted(evidence_urls - set(live_by_url))
        extra = sorted(set(live_by_url) - evidence_urls)
        raise ValueError(f"Live-check URL coverage mismatch; missing={missing}, extra={extra}")

    output: list[dict[str, Any]] = []
    for pilot in sorted(iosco_pilot, key=lambda row: int(row["pilot_rank"])):
        pilot_id = str(pilot["pilot_id"])
        evidence_rows = evidence_by_pilot.get(pilot_id, [])
        if len(evidence_rows) != int(pilot["reference_match_count"]):
            raise ValueError(f"Evidence count mismatch for {pilot_id}")
        references: list[dict[str, Any]] = []
        details: list[dict[str, Any]] = []
        for evidence in sorted(evidence_rows, key=lambda row: str(row["reference_record_id"])):
            record_id = str(evidence["reference_record_id"])
            reference = iosco_by_id.get(record_id)
            if reference is None:
                raise ValueError(f"Missing IOSCO index record {record_id} for {pilot_id}")
            matched_host = str(evidence["matched_reference_host"])
            if matched_host not in reference.get("observed_hosts", []):
                raise ValueError(f"Matched host {matched_host} is absent from IOSCO record {record_id}")
            if not host_is_same_or_subdomain(str(pilot["crimson_match_host"]), matched_host):
                raise ValueError(f"Unexpected host relationship for {pilot_id}")
            url = str(reference["notice_reference_url"])
            live = live_by_url[url]
            details.append(
                {
                    "reference_record_id": record_id,
                    "entity_names": [str(value) for value in reference.get("entity_name_keys", [])],
                    "observed_hosts": [str(value) for value in reference.get("observed_hosts", [])],
                    "regulator_name": str((reference.get("regulator") or {}).get("name") or ""),
                    "jurisdiction": str((reference.get("regulator") or {}).get("jurisdiction") or ""),
                    "warning_category": str((reference.get("warning_categories") or {}).get("detail") or ""),
                    "validation_date": str((reference.get("evidence_dates") or {}).get("validation_date") or ""),
                    "official_reference_url": url,
                    "live_check_status": str(live["status"]),
                    "live_check_reason": str(live["reason"]),
                    "quality_flags": [str(value) for value in reference.get("quality_flags", [])],
                }
            )
            references.append(reference)

        identity = identity_suggestion(references)
        live_status = aggregate_live_status(detail["live_check_status"] for detail in details)
        regulators = sorted({detail["regulator_name"] for detail in details if detail["regulator_name"]})
        jurisdictions = sorted({detail["jurisdiction"] for detail in details if detail["jurisdiction"]})
        entity_names = sorted({name for detail in details for name in detail["entity_names"]})
        categories = sorted({detail["warning_category"] for detail in details if detail["warning_category"]})
        latest_validation = max(detail["validation_date"] for detail in details)
        second_review_required = bool(pilot["shared_reference_host_present"]) or identity != "SAME_ENTITY"
        note = (
            f"AI-assisted first pass: {len(details)} IOSCO I-SCAN warning record(s) from "
            f"{', '.join(regulators)} reference {pilot['crimson_match_host']}; live URL status is {live_status}. "
            f"This supports {identity} and WARNING_RELEVANT only, not a conviction or automatic scam label. "
            "Human confirmation remains required."
        )
        output.append(
            {
                "pilot_id": pilot_id,
                "pilot_rank": int(pilot["pilot_rank"]),
                "review_stage": "AI_ASSISTED_FIRST_PASS",
                "review_status": "IN_PROGRESS",
                "official_reference_checked": "YES",
                "identity_relationship": identity,
                "evidence_assessment": "WARNING_RELEVANT",
                "reviewer": "Codex AI-assisted first pass",
                "reviewed_date": "2026-09-23",
                "review_notes": note,
                "second_review_status": "REQUESTED" if second_review_required else "NOT_REQUESTED",
                "second_reviewer": "",
                "human_confirmation_required": True,
                "manual_live_url_followup_required": live_status != "ALL_URLS_LIVE_CONFIRMED",
                "training_eligible": "NO",
                "label_created": False,
                "reference_source": "iosco_i_scan",
                "reference_record_ids": [detail["reference_record_id"] for detail in details],
                "reference_match_count": len(details),
                "crimson_host": str(pilot["crimson_match_host"]),
                "host_relations": [str(value) for value in pilot["host_relations"]],
                "shared_reference_host_present": bool(pilot["shared_reference_host_present"]),
                "entity_names": entity_names,
                "regulators": regulators,
                "jurisdictions": jurisdictions,
                "warning_categories": categories,
                "latest_validation_date": latest_validation,
                "live_reference_status": live_status,
                "reference_details": details,
                "source_version": references[0].get("source_version"),
                "source_raw_sha256": references[0].get("source_raw_sha256"),
            }
        )

    if len({row["pilot_id"] for row in output}) != 32:
        raise ValueError("IOSCO first-pass pilot IDs are not unique")
    if Counter(row["identity_relationship"] for row in output) != Counter({"SAME_ENTITY": 30, "IMPERSONATION_SUSPECTED": 2}):
        raise ValueError("Unexpected identity suggestion counts")
    return output


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing review artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in records)
    path.write_text(payload, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", type=Path, default=DEFAULT_PILOT)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--iosco-index", type=Path, default=DEFAULT_IOSCO_INDEX)
    parser.add_argument("--live-checks", type=Path, default=DEFAULT_LIVE_CHECKS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    live_check = json.loads(args.live_checks.read_text(encoding="utf-8"))
    records = prepare_records(load_jsonl(args.pilot), load_jsonl(args.evidence), load_jsonl(args.iosco_index), live_check)
    write_jsonl(args.output, records)
    print(json.dumps({
        "output": str(args.output),
        "record_count": len(records),
        "sha256": sha256_file(args.output),
        "identity_relationship_counts": dict(Counter(row["identity_relationship"] for row in records)),
        "live_reference_status_counts": dict(Counter(row["live_reference_status"] for row in records)),
        "second_review_requested_count": sum(row["second_review_status"] == "REQUESTED" for row in records),
        "training_eligible_count": 0,
        "labels_created": 0,
    }, indent=2))


if __name__ == "__main__":
    main()
