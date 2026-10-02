"""Merge hash-pinned V2 candidate queues without changing candidate state."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.matching.external_domain_references import load_jsonl, write_jsonl
from src.isi.normalization.external_references import sha256_file


def merge_queues(queues: list[list[dict[str, object]]]) -> list[dict[str, object]]:
    rows = [row for queue in queues for row in queue]
    ids = [str(row["candidate_id"]) for row in rows]
    hosts = [str(row["candidate_host"]).casefold().rstrip(".") for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Candidate IDs overlap across queues")
    if len(hosts) != len(set(hosts)):
        raise ValueError("Candidate hosts overlap across queues")
    if any(row.get("label_created") is not False or row.get("training_eligible") != "NO" for row in rows):
        raise ValueError("Merged queue contains a label or training-eligible row")
    return sorted(rows, key=lambda row: str(row["candidate_id"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", nargs=2, action="append", metavar=("PATH", "SHA256"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.output, args.report):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite frozen output: {path}")
    queues = []
    inputs = []
    for raw_path, expected_hash in args.input:
        path = Path(raw_path)
        actual = sha256_file(path)
        if actual != expected_hash:
            raise ValueError(f"Queue SHA-256 mismatch: {path}")
        rows = load_jsonl(path)
        queues.append(rows)
        inputs.append({"path": str(path), "sha256": actual, "record_count": len(rows)})
    merged = merge_queues(queues)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output, merged)
    report = {
        "analysis_id": "EXTERNAL_TEXT_WAYBACK_COMBINED_CANDIDATE_QUEUE_V2",
        "status": "FROZEN_UNLABELED_COMBINED_QUEUE",
        "inputs": inputs,
        "counts": {
            "record_count": len(merged),
            "unique_candidate_id_count": len({row["candidate_id"] for row in merged}),
            "unique_candidate_host_count": len({row["candidate_host"] for row in merged}),
            "labels_created": 0,
        },
        "output": {"path": str(args.output), "sha256": sha256_file(args.output)},
        "training_allowed": False,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
