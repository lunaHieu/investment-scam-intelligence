"""Build an untouched, balanced candidate queue for Wayback/language expansion V2."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.select_external_text_capture_candidates import _load_frozen_index
from src.isi.curation.external_text_capture_queue import (
    select_confirmed_reserve_candidates,
    select_legitimate_reserve_candidates,
)
from src.isi.matching.external_domain_references import load_jsonl, write_jsonl
from src.isi.normalization.external_references import sha256_file


DEFAULT_PROTOCOL = ROOT / "configs" / "external_text_wayback_language_expansion_v2.json"


def normalized_host(value: object) -> str:
    host = str(value or "").strip().casefold().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def load_excluded_hosts(protocol: dict[str, object]) -> tuple[set[str], list[dict[str, object]]]:
    hosts: set[str] = set()
    inputs: list[dict[str, object]] = []
    for item in protocol["prior_candidate_queues"]:
        path = Path(str(item["path"]))
        actual_hash = sha256_file(path)
        if actual_hash != item["sha256"]:
            raise ValueError(f"Prior queue hash mismatch for {path}: {actual_hash}")
        rows = load_jsonl(path)
        if len(rows) != item["record_count"]:
            raise ValueError(f"Prior queue count mismatch for {path}: {len(rows)}")
        queue_hosts = {normalized_host(row.get("candidate_host")) for row in rows}
        if "" in queue_hosts:
            raise ValueError(f"Prior queue contains a missing candidate_host: {path}")
        hosts.update(queue_hosts)
        inputs.append(
            {
                "path": str(path),
                "sha256": actual_hash,
                "record_count": len(rows),
                "unique_host_count": len(queue_hosts),
            }
        )
    return hosts, inputs


def to_acquisition_row(
    row: dict[str, object], *, branch: str, rank: int, target_timestamp: str
) -> dict[str, object]:
    prefix = "CONF" if branch == "CONFIRMED_CANDIDATE" else "LEGIT"
    return {
        "candidate_id": f"MATCHWB2_{prefix}_{rank:03d}",
        "source_candidate_id": row["candidate_id"],
        "source_case_id": f"LANGEXP2_{row['source_record_id']}",
        "reference_branch": branch,
        "reference_branch_is_ground_truth": False,
        "candidate_host": normalized_host(row["candidate_host"]),
        "source_id": row["source_id"],
        "source_record_id": str(row["source_record_id"]),
        "entity_name_keys": list(row["entity_name_keys"]),
        "official_reference": row["official_reference"],
        "target_timestamp": target_timestamp,
        "archive_acquisition_state": "NEEDS_ARCHIVE_QUERY",
        "language_stratum": "UNASSIGNED_BEFORE_TEXT_EXTRACTION",
        "first_review_required": True,
        "independent_blinded_second_review_required": True,
        "label_created": False,
        "training_eligible": "NO",
    }


def build_queue(
    protocol: dict[str, object],
    iosco_records: list[dict[str, object]],
    sec_records: list[dict[str, object]],
    excluded_hosts: set[str],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    selection = protocol["selection"]
    per_branch = int(selection["requested_per_reference_branch"])
    seed = str(selection["seed"])
    target_timestamp = str(selection["target_timestamp"])
    if len(target_timestamp) != 8 or not target_timestamp.isdigit():
        raise ValueError("target_timestamp must be YYYYMMDD")

    confirmed, confirmed_report = select_confirmed_reserve_candidates(
        iosco_records,
        excluded_hosts,
        reserve_size=per_branch,
        seed=f"{seed}-confirmed",
        candidate_id_prefix="LANGEXP2_SOURCE_CONF",
    )
    legitimate, legitimate_report = select_legitimate_reserve_candidates(
        iosco_records,
        sec_records,
        excluded_hosts,
        reserve_size=per_branch,
        seed=f"{seed}-legitimate",
    )
    queue = [
        to_acquisition_row(row, branch="CONFIRMED_CANDIDATE", rank=rank, target_timestamp=target_timestamp)
        for rank, row in enumerate(confirmed, start=1)
    ] + [
        to_acquisition_row(row, branch="LEGITIMATE_CANDIDATE", rank=rank, target_timestamp=target_timestamp)
        for rank, row in enumerate(legitimate, start=1)
    ]
    queue_hosts = [normalized_host(row["candidate_host"]) for row in queue]
    if len(queue_hosts) != len(set(queue_hosts)):
        raise ValueError("V2 queue contains duplicate candidate hosts")
    overlap = sorted(set(queue_hosts) & excluded_hosts)
    if overlap:
        raise ValueError(f"V2 queue overlaps prior candidate hosts: {overlap}")
    if any(row["label_created"] or row["training_eligible"] != "NO" for row in queue):
        raise ValueError("Candidate queue must remain unlabeled and training-ineligible")
    report = {
        "confirmed_selection": confirmed_report,
        "legitimate_selection": legitimate_report,
        "selected_counts": {
            "CONFIRMED_CANDIDATE": len(confirmed),
            "LEGITIMATE_CANDIDATE": len(legitimate),
            "total": len(queue),
        },
        "unique_selected_host_count": len(set(queue_hosts)),
        "prior_host_overlap_count": 0,
    }
    return queue, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--queue-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.queue_output, args.report):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite frozen output: {path}")

    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    if protocol.get("status") != "LOCKED_BEFORE_ACQUISITION":
        raise ValueError("Protocol is not locked before acquisition")
    iosco_records, iosco_input = _load_frozen_index(Path(protocol["source_indices"]["iosco_registry"]))
    sec_records, sec_input = _load_frozen_index(Path(protocol["source_indices"]["sec_registry"]))
    excluded_hosts, prior_inputs = load_excluded_hosts(protocol)
    queue, selection_report = build_queue(protocol, iosco_records, sec_records, excluded_hosts)

    args.queue_output.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.queue_output, queue)
    report = {
        "queue_id": "EXTERNAL_TEXT_WAYBACK_LANGUAGE_EXPANSION_QUEUE_V2",
        "created_at": "2026-09-30",
        "status": "FROZEN_UNLABELED_ARCHIVE_QUERY_REQUIRED",
        "protocol": {"path": str(args.protocol), "sha256": sha256_file(args.protocol)},
        "inputs": {
            "iosco": iosco_input,
            "sec_iapd": sec_input,
            "prior_candidate_queues": prior_inputs,
            "unique_excluded_host_count": len(excluded_hosts),
        },
        "selection": selection_report,
        "output": {
            "path": str(args.queue_output),
            "sha256": sha256_file(args.queue_output),
            "record_count": len(queue),
        },
        "safety_contract": {
            "network_operations": 0,
            "candidate_live_domain_access_operations": 0,
            "labels_created": 0,
            "model_scoring_operations": 0,
            "training_allowed": False,
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
