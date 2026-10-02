"""Build a fresh unlabeled Wayback holdout V3 queue disjoint from all prior hosts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_external_text_wayback_language_queue_v2 import (  # noqa: E402
    load_excluded_hosts,
    normalized_host,
)
from scripts.select_external_text_capture_candidates import _load_frozen_index  # noqa: E402
from src.isi.curation.external_text_capture_queue import (  # noqa: E402
    select_confirmed_reserve_candidates,
    select_legitimate_reserve_candidates,
)
from src.isi.matching.external_domain_references import write_jsonl  # noqa: E402
from src.isi.normalization.external_references import sha256_file  # noqa: E402


DEFAULT_PROTOCOL = ROOT / "configs" / "external_text_wayback_holdout_v3.json"


def to_acquisition_row(
    row: dict[str, object], *, branch: str, rank: int, target_timestamp: str
) -> dict[str, object]:
    prefix = "CONF" if branch == "CONFIRMED_CANDIDATE" else "LEGIT"
    return {
        "candidate_id": f"MATCHWB3_{prefix}_{rank:03d}",
        "source_candidate_id": row["candidate_id"],
        "source_case_id": f"HOLDOUT3_{row['source_record_id']}",
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
        "primary_review_required": True,
        "independent_blinded_second_review_required": True,
        "label_created": False,
        "training_eligible": "NO",
        "model_scoring_eligible": "NO_BEFORE_FROZEN_BENCHMARK_AND_OWNER_ACCEPTANCE",
    }


def load_opened_benchmark_hosts(protocol: dict[str, object]) -> tuple[set[str], dict[str, object]]:
    item = protocol["opened_benchmark"]
    path = Path(str(item["path"]))
    actual_hash = sha256_file(path)
    if actual_hash != item["sha256"]:
        raise ValueError("Opened benchmark hash mismatch")
    benchmark = json.loads(path.read_text(encoding="utf-8"))
    records = benchmark.get("records", [])
    if len(records) != item["record_count"]:
        raise ValueError("Opened benchmark record count mismatch")
    hosts = {
        normalized_host(record.get("artifact", {}).get("candidate_host"))
        for record in records
    }
    if "" in hosts or len(hosts) != len(records):
        raise ValueError("Opened benchmark hosts are missing or duplicated")
    return hosts, {
        "path": str(path),
        "sha256": actual_hash,
        "record_count": len(records),
        "unique_host_count": len(hosts),
    }


def build_queue(protocol, iosco_records, sec_records, excluded_hosts):
    selection = protocol["selection"]
    per_branch = int(selection["requested_per_reference_branch"])
    seed = str(selection["seed"])
    timestamp = str(selection["target_timestamp"])
    if len(timestamp) != 8 or not timestamp.isdigit():
        raise ValueError("target_timestamp must be YYYYMMDD")
    confirmed, confirmed_report = select_confirmed_reserve_candidates(
        iosco_records,
        excluded_hosts,
        reserve_size=per_branch,
        seed=f"{seed}-confirmed",
        candidate_id_prefix="HOLDOUT3_SOURCE_CONF",
    )
    legitimate, legitimate_report = select_legitimate_reserve_candidates(
        iosco_records,
        sec_records,
        excluded_hosts,
        reserve_size=per_branch,
        seed=f"{seed}-legitimate",
    )
    queue = [
        to_acquisition_row(
            row, branch="CONFIRMED_CANDIDATE", rank=index, target_timestamp=timestamp
        )
        for index, row in enumerate(confirmed, start=1)
    ] + [
        to_acquisition_row(
            row, branch="LEGITIMATE_CANDIDATE", rank=index, target_timestamp=timestamp
        )
        for index, row in enumerate(legitimate, start=1)
    ]
    hosts = [row["candidate_host"] for row in queue]
    if len(queue) != per_branch * 2:
        raise ValueError("Candidate selector returned an incomplete V3 queue")
    if len(hosts) != len(set(hosts)):
        raise ValueError("V3 queue contains duplicate candidate hosts")
    overlap = sorted(set(hosts) & excluded_hosts)
    if overlap:
        raise ValueError(f"V3 queue overlaps excluded hosts: {overlap[:5]}")
    if any(
        row["label_created"]
        or row["training_eligible"] != "NO"
        or not str(row["model_scoring_eligible"]).startswith("NO_")
        for row in queue
    ):
        raise ValueError("V3 candidate queue must remain unlabeled and model-ineligible")
    return queue, {
        "confirmed_selection": confirmed_report,
        "legitimate_selection": legitimate_report,
        "selected_counts": {
            "CONFIRMED_CANDIDATE": len(confirmed),
            "LEGITIMATE_CANDIDATE": len(legitimate),
            "total": len(queue),
        },
        "unique_selected_host_count": len(set(hosts)),
        "prior_host_overlap_count": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--queue-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.queue_output, args.report):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite frozen output: {path}")
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    if protocol.get("protocol_id") != "EXTERNAL_TEXT_WAYBACK_HOLDOUT_V3":
        raise ValueError("Unexpected protocol ID")
    if protocol.get("status") != "LOCKED_BEFORE_ACQUISITION":
        raise ValueError("V3 protocol is not locked before acquisition")
    iosco_records, iosco_input = _load_frozen_index(
        ROOT / str(protocol["source_indices"]["iosco_registry"])
    )
    sec_records, sec_input = _load_frozen_index(
        ROOT / str(protocol["source_indices"]["sec_registry"])
    )
    excluded_hosts, prior_inputs = load_excluded_hosts(protocol)
    opened_hosts, opened_input = load_opened_benchmark_hosts(protocol)
    if not opened_hosts.issubset(excluded_hosts):
        raise ValueError("Opened benchmark is not fully covered by prior host exclusions")
    queue, selection_report = build_queue(
        protocol, iosco_records, sec_records, excluded_hosts
    )
    selected_hosts = {row["candidate_host"] for row in queue}
    if selected_hosts & opened_hosts:
        raise ValueError("V3 candidate queue overlaps the opened V2 benchmark")
    args.queue_output.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.queue_output, queue)
    report = {
        "queue_id": "EXTERNAL_TEXT_WAYBACK_HOLDOUT_V3_QUEUE",
        "created_at": "2026-10-02",
        "status": "FROZEN_UNLABELED_ARCHIVE_QUERY_REQUIRED",
        "protocol": {"path": str(args.protocol), "sha256": sha256_file(args.protocol)},
        "inputs": {
            "iosco": iosco_input,
            "sec_iapd": sec_input,
            "prior_candidate_queues": prior_inputs,
            "opened_benchmark": opened_input,
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
            "opened_benchmark_record_reuse_count": 0,
            "labels_created": 0,
            "model_scoring_operations": 0,
            "training_allowed": False,
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
