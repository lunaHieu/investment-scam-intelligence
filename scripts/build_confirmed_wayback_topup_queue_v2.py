"""Build an untouched confirmed-candidate top-up queue after V2 text attrition."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_external_text_wayback_language_queue_v2 import load_excluded_hosts, normalized_host
from scripts.select_external_text_capture_candidates import _load_frozen_index
from src.isi.curation.external_text_capture_queue import select_confirmed_reserve_candidates
from src.isi.matching.external_domain_references import write_jsonl
from src.isi.normalization.external_references import sha256_file


DEFAULT_PROTOCOL = ROOT / "configs" / "external_text_wayback_confirmed_topup_v2.json"


def to_topup_row(
    row: dict[str, object],
    rank: int,
    target_timestamp: str,
    candidate_id_prefix: str = "MATCHWB2_TOPUP_CONF",
) -> dict[str, object]:
    return {
        "candidate_id": f"{candidate_id_prefix}_{rank:03d}",
        "source_candidate_id": row["candidate_id"],
        "source_case_id": f"LANGEXP2_TOPUP_{row['source_record_id']}",
        "reference_branch": "CONFIRMED_CANDIDATE",
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
    if protocol.get("status") != "LOCKED_BEFORE_TOPUP_ACQUISITION":
        raise ValueError("Top-up protocol is not locked")
    trigger = protocol["trigger"]
    if sha256_file(Path(trigger["corrected_language_screening_report"])) != trigger["sha256"]:
        raise ValueError("Corrected language-screening trigger hash mismatch")
    iosco, iosco_input = _load_frozen_index(
        ROOT / "registry" / "analyses" / "iosco_warning_reference_index_v1.json"
    )
    excluded, excluded_inputs = load_excluded_hosts(protocol)
    selection = protocol["selection"]
    requested = int(selection["requested_confirmed_candidates"])
    selected, selection_report = select_confirmed_reserve_candidates(
        iosco,
        excluded,
        reserve_size=requested,
        seed=str(selection["seed"]),
        candidate_id_prefix="LANGEXP2_TOPUP_SOURCE_CONF",
    )
    candidate_id_prefix = str(selection.get("candidate_id_prefix", "MATCHWB2_TOPUP_CONF"))
    queue = [
        to_topup_row(
            row,
            rank,
            str(selection["target_timestamp"]),
            candidate_id_prefix=candidate_id_prefix,
        )
        for rank, row in enumerate(selected, start=1)
    ]
    hosts = {row["candidate_host"] for row in queue}
    if len(hosts) != len(queue) or hosts & excluded:
        raise ValueError("Top-up host uniqueness or exclusion contract failed")
    args.queue_output.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.queue_output, queue)
    report = {
        "queue_id": "EXTERNAL_TEXT_WAYBACK_CONFIRMED_TOPUP_QUEUE_V2",
        "created_at": "2026-10-01",
        "status": "FROZEN_UNLABELED_ARCHIVE_QUERY_REQUIRED",
        "protocol": {"path": str(args.protocol), "sha256": sha256_file(args.protocol)},
        "inputs": {
            "iosco": iosco_input,
            "prior_candidate_queues": excluded_inputs,
            "unique_excluded_host_count": len(excluded),
        },
        "selection": selection_report,
        "output": {
            "path": str(args.queue_output),
            "sha256": sha256_file(args.queue_output),
            "record_count": len(queue),
        },
        "safety_contract": {
            "network_operations": 0,
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
