"""Select unused SEC/IAPD reserve hosts for matched Wayback acquisition."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for value in (ROOT, SCRIPTS):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

from validate_external_text_intake import sha256_file


def load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def select_supplement(
    reserve_rows: list[dict[str, object]], excluded_hosts: set[str], limit: int
) -> list[dict[str, object]]:
    eligible = [
        row
        for row in reserve_rows
        if row.get("target_outcome") == "LEGITIMATE_RESERVE_CANDIDATE"
        and str(row.get("candidate_host", "")).casefold() not in excluded_hosts
        and row.get("official_reference", {}).get("registration", {}).get("firm_type") == "Registered"
        and row.get("official_reference", {}).get("registration", {}).get("status") == "APPROVED"
    ]
    eligible.sort(key=lambda row: (int(row["selection_rank_within_target"]), row["candidate_id"]))
    selected = eligible[:limit]
    return [
        {
            "candidate_id": f"MATCHWB_SUPP_{row['candidate_id']}",
            "source_candidate_id": row["candidate_id"],
            "source_case_id": f"SUPPLEMENT_{row['candidate_id']}",
            "reference_branch": "LEGITIMATE_CANDIDATE",
            "prior_reconciliation_status": "NONE",
            "candidate_host": row["candidate_host"],
            "source_record_id": str(row["source_record_id"]),
            "target_timestamp": "20260924",
            "archive_acquisition_state": "NEEDS_ARCHIVE_QUERY",
            "entity_name_keys": list(row["entity_name_keys"]),
            "official_reference": row["official_reference"],
            "first_review_required": True,
            "independent_second_review_required": True,
            "label_created": False,
        }
        for row in selected
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reserve-queue", type=Path, required=True)
    parser.add_argument("--reserve-sha256", required=True)
    parser.add_argument("--main-queue", type=Path, required=True)
    parser.add_argument("--main-queue-sha256", required=True)
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.output, args.report):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite frozen output: {path}")
    if sha256_file(args.reserve_queue) != args.reserve_sha256:
        raise ValueError("Reserve queue SHA-256 mismatch")
    if sha256_file(args.main_queue) != args.main_queue_sha256:
        raise ValueError("Main queue SHA-256 mismatch")
    excluded = {str(row["candidate_host"]).casefold() for row in load_jsonl(args.main_queue)}
    selected = select_supplement(load_jsonl(args.reserve_queue), excluded, args.limit)
    if len(selected) != args.limit:
        raise ValueError(f"Expected {args.limit} supplemental candidates, found {len(selected)}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for item in selected:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    report = {
        "queue_id": "EXTERNAL_TEXT_MATCHED_WAYBACK_LEGITIMATE_SUPPLEMENT_V1",
        "status": "ARCHIVE_ACQUISITION_REQUIRED_UNLABELED",
        "selection": {
            "limit": args.limit,
            "excluded_existing_host_count": len(excluded),
            "selected_count": len(selected),
            "first_review_required": True,
            "independent_second_review_required": True,
        },
        "output": {"path": str(args.output), "sha256": sha256_file(args.output)},
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
