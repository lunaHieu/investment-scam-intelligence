"""Create a zero-network pending availability report for a frozen acquisition queue."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.matching.external_domain_references import load_jsonl
from src.isi.normalization.external_references import sha256_file


def pending_result(row: dict[str, object]) -> dict[str, object]:
    return {
        "candidate_id": str(row["candidate_id"]),
        "candidate_host": str(row["candidate_host"]).casefold().rstrip("."),
        "source_case_id": str(row["source_case_id"]),
        "reference_branch": str(row["reference_branch"]),
        "query_timestamp": str(row["target_timestamp"]),
        "available": False,
        "snapshot_timestamp": None,
        "snapshot_url": None,
        "error": "PENDING_NETWORK_QUERY_NOT_AN_AVAILABILITY_RESULT",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--queue-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {args.output}")
    if sha256_file(args.queue) != args.queue_sha256:
        raise ValueError("Queue SHA-256 mismatch")
    queue = load_jsonl(args.queue)
    results = [pending_result(row) for row in queue]
    if len({row["candidate_id"] for row in results}) != len(results):
        raise ValueError("Queue contains duplicate candidate IDs")
    counts = Counter(row["reference_branch"] for row in results)
    report = {
        "report_id": "WAYBACK_LANGUAGE_EXPANSION_AVAILABILITY_V2_CONFIRMED_TOPUP_PENDING",
        "created_at": "2026-10-01",
        "queue_path": str(args.queue),
        "queue_sha256": args.queue_sha256,
        "requested_candidate_count": len(results),
        "requested_by_reference_branch": dict(sorted(counts.items())),
        "network_request_count": 0,
        "available_snapshot_count": 0,
        "available_by_reference_branch": {branch: 0 for branch in counts},
        "unresolved_error_count": len(results),
        "acquisition_ready": False,
        "results": results,
        "safety_contract": {
            "network_operations": 0,
            "candidate_live_domain_access_operations": 0,
            "labels_created": 0,
            "model_scoring_operations": 0,
            "training_allowed": False,
            "pending_errors_are_not_interpreted_as_no_snapshot": True,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "OK", "output": str(args.output), "sha256": sha256_file(args.output), "pending_count": len(results)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
