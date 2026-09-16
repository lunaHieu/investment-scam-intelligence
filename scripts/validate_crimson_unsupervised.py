"""Validate Crimson unlabeled assignments, review queue and analysis report."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    root = args.report.parent
    assignments_path = root / "domain_assignments.jsonl"
    queue_path = root / "review_queue_100.jsonl"
    assignments = load_jsonl(assignments_path)
    queue = load_jsonl(queue_path)
    errors = []

    if report.get("network_operations") != 0 or report.get("labels_created") != 0:
        errors.append("analysis must have zero network operations and zero labels")
    if report.get("training_allowed") is not False:
        errors.append("training_allowed must remain false")
    if len(assignments) != report.get("record_count"):
        errors.append("assignment count differs from report")
    artifact_ids = [item.get("artifact_id") for item in assignments]
    domains = [item.get("domain") for item in assignments]
    ranks = [item.get("anomaly_rank") for item in assignments]
    if len(set(artifact_ids)) != len(assignments) or len(set(domains)) != len(assignments):
        errors.append("assignments contain duplicate artifacts or domains")
    if sorted(ranks) != list(range(1, len(assignments) + 1)):
        errors.append("anomaly ranks are not a complete unique sequence")
    cluster_count = report.get("cluster_selection", {}).get("selected_cluster_count")
    if set(item.get("cluster_id") for item in assignments) != set(range(cluster_count)):
        errors.append("assignment cluster IDs do not match selected cluster count")
    if len(queue) != 100 or len({item.get("domain") for item in queue}) != 100:
        errors.append("review queue must contain 100 unique domains")
    reason_counts = Counter(item.get("queue_reason") for item in queue)
    if reason_counts != Counter({"LEXICAL_OUTLIER": 50, "CLUSTER_REPRESENTATIVE": 50}):
        errors.append("review queue must contain 50 outliers and 50 representatives")
    assignment_domains = set(domains)
    if any(item.get("domain") not in assignment_domains for item in queue):
        errors.append("review queue contains a domain outside assignments")
    for item in queue:
        if item.get("review_status") != "UNREVIEWED" or "not a scam label" not in item.get("interpretation", ""):
            errors.append("queue item has invalid review status or interpretation")
            break
    expected = report.get("outputs", {})
    if sha256_file(assignments_path) != expected.get("assignments_sha256"):
        errors.append("assignment SHA-256 mismatch")
    if sha256_file(queue_path) != expected.get("review_queue_sha256"):
        errors.append("review queue SHA-256 mismatch")

    result = {
        "status": "VALID" if not errors else "INVALID",
        "record_count": len(assignments),
        "cluster_count": cluster_count,
        "queue_reason_counts": dict(reason_counts),
        "network_operations": report.get("network_operations"),
        "labels_created": report.get("labels_created"),
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
