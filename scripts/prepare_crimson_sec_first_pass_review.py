"""Prepare an evidence-backed, non-label SEC first pass for the Crimson pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PILOT = Path(
    r"D:\nckh 2026-2027\ISI_Data\curated\crimson_external_reference_review_pilot_v1\pilot_records_v1.jsonl"
)
DEFAULT_EVIDENCE = Path(
    r"D:\nckh 2026-2027\ISI_Data\curated\crimson_external_reference_review_pilot_v1\evidence_records_v1.jsonl"
)
DEFAULT_SEC_INDEX = Path(
    r"D:\nckh 2026-2027\ISI_Data\derived\external_reference_indices_v1\sec_registration_reference_v1.jsonl"
)
DEFAULT_OUTPUT = Path(
    r"D:\nckh 2026-2027\ISI_Data\curated\crimson_external_reference_review_pilot_v1\sec_ai_assisted_first_pass_v1.jsonl"
)


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


def prepare_records(
    pilot_records: Iterable[dict[str, Any]],
    evidence_records: Iterable[dict[str, Any]],
    sec_records: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    sec_pilot = [row for row in pilot_records if row.get("reference_sources") == ["sec_iapd"]]
    if len(sec_pilot) != 8:
        raise ValueError(f"Expected 8 SEC pilot rows, received {len(sec_pilot)}")

    evidence_by_pilot = {
        row["pilot_id"]: row
        for row in evidence_records
        if row.get("match_source_id") == "sec_iapd"
    }
    sec_by_id = {str(row["source_record_id"]): row for row in sec_records}
    output: list[dict[str, Any]] = []

    for pilot in sorted(sec_pilot, key=lambda row: int(row["pilot_rank"])):
        pilot_id = str(pilot["pilot_id"])
        evidence = evidence_by_pilot.get(pilot_id)
        if evidence is None:
            raise ValueError(f"Missing SEC evidence for {pilot_id}")
        source_record_id = str(evidence["reference_record_id"])
        reference = sec_by_id.get(source_record_id)
        if reference is None:
            raise ValueError(f"Missing SEC index record {source_record_id} for {pilot_id}")

        crimson_host = str(pilot["crimson_match_host"])
        matched_host = str(evidence["matched_reference_host"])
        observed_hosts = [str(host) for host in reference.get("observed_hosts", [])]
        if matched_host not in observed_hosts:
            raise ValueError(f"Matched host {matched_host} is not present in SEC record {source_record_id}")
        if not host_is_same_or_subdomain(crimson_host, matched_host):
            raise ValueError(f"Unexpected host relationship for {pilot_id}: {crimson_host} / {matched_host}")

        registration = reference.get("registration") or {}
        filing = reference.get("filing") or {}
        entity_names = [str(name) for name in reference.get("entity_name_keys", [])]
        relation = str(evidence["host_relation"])
        note = (
            f"AI-assisted first pass: SEC/IAPD CRD {source_record_id} "
            f"({reference['sec_number']}) lists {', '.join(entity_names)} and host {matched_host}; "
            f"the Crimson host relationship is {relation}. The snapshot reports "
            f"{registration.get('firm_type', 'unknown type')} / {registration.get('status', 'unknown status')} "
            f"with filing date {filing.get('date', 'unknown')}. This supports SAME_ENTITY and "
            "REGISTRATION_RELEVANT only; it is not a legitimacy or content-safety label. "
            "Human confirmation remains required."
        )
        output.append(
            {
                "pilot_id": pilot_id,
                "pilot_rank": int(pilot["pilot_rank"]),
                "review_stage": "AI_ASSISTED_FIRST_PASS",
                "review_status": "IN_PROGRESS",
                "official_reference_checked": "YES",
                "identity_relationship": "SAME_ENTITY",
                "evidence_assessment": "REGISTRATION_RELEVANT",
                "reviewer": "Codex AI-assisted first pass",
                "reviewed_date": "2026-09-23",
                "review_notes": note,
                "second_review_status": "NOT_REQUESTED",
                "second_reviewer": "",
                "human_confirmation_required": True,
                "training_eligible": "NO",
                "label_created": False,
                "reference_source": "sec_iapd",
                "reference_record_id": source_record_id,
                "sec_number": str(reference["sec_number"]),
                "official_reference_url": f"https://adviserinfo.sec.gov/firm/summary/{source_record_id}",
                "entity_names": entity_names,
                "matched_reference_host": matched_host,
                "crimson_host": crimson_host,
                "host_relation": relation,
                "registration_type": registration.get("firm_type"),
                "registration_status": registration.get("status"),
                "registration_date": registration.get("date"),
                "filing_date": filing.get("date"),
                "source_version": reference.get("source_version"),
                "source_raw_sha256": reference.get("source_raw_sha256"),
            }
        )

    if len({row["pilot_id"] for row in output}) != 8:
        raise ValueError("SEC first-pass pilot IDs are not unique")
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
    parser.add_argument("--sec-index", type=Path, default=DEFAULT_SEC_INDEX)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    records = prepare_records(
        load_jsonl(args.pilot),
        load_jsonl(args.evidence),
        load_jsonl(args.sec_index),
    )
    write_jsonl(args.output, records)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "record_count": len(records),
                "sha256": sha256_file(args.output),
                "review_status_counts": {"IN_PROGRESS": len(records)},
                "training_eligible_count": 0,
                "labels_created": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
