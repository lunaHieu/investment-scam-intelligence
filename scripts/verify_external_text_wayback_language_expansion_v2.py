"""Verify the frozen V2 candidate queue and its partial Wayback availability checkpoint."""

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


def verify(registry: dict[str, object]) -> dict[str, object]:
    inputs = {item["role"]: item for item in registry["inputs"]}
    outputs = {item["role"]: item for item in registry["outputs"]}
    for item in [*inputs.values(), *outputs.values(), *registry["implementation"]]:
        path = Path(str(item["path"]))
        if not path.is_file():
            raise ValueError(f"Missing pinned file: {path}")
        actual = sha256_file(path)
        if actual != item["sha256"]:
            raise ValueError(f"SHA-256 mismatch for {path}: {actual}")

    protocol = json.loads(Path(inputs["protocol"]["path"]).read_text(encoding="utf-8"))
    queue = load_jsonl(Path(outputs["candidate_queue"]["path"]))
    queue_report = json.loads(Path(outputs["candidate_queue_report"]["path"]).read_text(encoding="utf-8"))
    availability = json.loads(Path(outputs["partial_availability_report"]["path"]).read_text(encoding="utf-8"))
    if len(queue) != outputs["candidate_queue"]["record_count"] or len(queue) != 120:
        raise ValueError("Unexpected candidate queue size")
    counts = Counter(row["reference_branch"] for row in queue)
    if counts != {"CONFIRMED_CANDIDATE": 60, "LEGITIMATE_CANDIDATE": 60}:
        raise ValueError(f"Unbalanced candidate branches: {counts}")
    hosts = [row["candidate_host"].casefold().rstrip(".") for row in queue]
    if len(hosts) != len(set(hosts)):
        raise ValueError("Candidate hosts are not unique")
    if any(row["label_created"] or row["training_eligible"] != "NO" for row in queue):
        raise ValueError("Queue contains a label or training-eligible row")
    if queue_report["selection"]["prior_host_overlap_count"] != 0:
        raise ValueError("Queue overlaps a prior candidate host")
    if availability["queue_sha256"] != outputs["candidate_queue"]["sha256"]:
        raise ValueError("Availability report does not bind to the candidate queue")
    if len(availability["results"]) != len(queue):
        raise ValueError("Availability report lacks exact candidate coverage")
    ids = {row["candidate_id"] for row in queue}
    result_ids = {row["candidate_id"] for row in availability["results"]}
    if result_ids != ids:
        raise ValueError("Availability result IDs do not match the queue")
    errors = sum(bool(row.get("error")) for row in availability["results"])
    definitive_no_snapshot = sum(
        not row.get("available") and not row.get("error") for row in availability["results"]
    )
    available = sum(bool(row.get("available")) for row in availability["results"])
    if available + definitive_no_snapshot + errors != len(queue):
        raise ValueError("Availability outcomes are not mutually exhaustive")
    if registry["readiness"]["capture_allowed"] != (errors == 0):
        raise ValueError("Registry capture gate does not match unresolved error state")
    if protocol["model_firewall"]["model_scoring_allowed_before_frozen_benchmark"]:
        raise ValueError("Model firewall is open")
    return {
        "status": "OK",
        "candidate_count": len(queue),
        "branch_counts": dict(sorted(counts.items())),
        "unique_host_count": len(set(hosts)),
        "available_snapshot_count": available,
        "definitive_no_snapshot_count": definitive_no_snapshot,
        "unresolved_error_count": errors,
        "capture_allowed": errors == 0,
        "labels_created": 0,
        "model_scoring_operations": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    print(json.dumps(verify(registry), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
