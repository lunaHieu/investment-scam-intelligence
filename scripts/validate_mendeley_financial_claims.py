"""Validate Financial Claims V1 outputs against the frozen group-split CSV."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

from extract_mendeley_financial_claims import (
    ALLOWED_PARTITIONS,
    FEATURE_VERSION,
    SIGNAL_TYPES,
    extract_signals,
    rule_set_sha256,
)


FORBIDDEN_KEYS = {
    "label",
    "source_label",
    "source_dataset",
    "original_partition",
    "ground_truth_status",
    "label_confidence",
    "review_notes",
    "verification_status",
}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Frozen group-split CSV")
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--review-queue", type=Path, required=True)
    args = parser.parse_args()

    source: dict[str, tuple[str, str, str]] = {}
    test_count = 0
    with args.input.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            partition = (row.get("partition") or "").strip().lower()
            if partition == "test":
                test_count += 1
                continue
            if partition in ALLOWED_PARTITIONS:
                source[row["record_id"]] = (partition, row["split_group_id"], row.get("text_content") or "")

    feature_ids: set[str] = set()
    partition_counts: Counter[str] = Counter()
    candidate_count = 0
    with args.features.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            record = json.loads(line)
            if FORBIDDEN_KEYS.intersection(record) or FORBIDDEN_KEYS.intersection(record.get("features", {})):
                raise ValueError(f"line {line_number}: forbidden leakage or label field")
            record_id = record.get("record_id")
            if record_id in feature_ids or record_id not in source:
                raise ValueError(f"line {line_number}: unexpected or duplicate record_id")
            partition, group_id, text = source[record_id]
            if record.get("partition") != partition or record.get("split_group_id") != group_id:
                raise ValueError(f"line {line_number}: partition/group provenance mismatch")
            if record.get("feature_version") != FEATURE_VERSION:
                raise ValueError(f"line {line_number}: wrong feature version")
            signals, features = extract_signals(text)
            expected_types = sorted({str(item["signal_type"]) for item in signals})
            if record.get("signals") != signals or record.get("features") != features:
                raise ValueError(f"line {line_number}: deterministic recomputation mismatch")
            if record.get("signal_types") != expected_types:
                raise ValueError(f"line {line_number}: signal type summary mismatch")
            if signals:
                candidate_count += 1
            feature_ids.add(record_id)
            partition_counts[partition] += 1

    if feature_ids != set(source):
        raise ValueError("Feature output does not cover every train/validation record exactly once")

    queue_ids: set[str] = set()
    queue_groups: set[str] = set()
    queue_reasons: Counter[str] = Counter()
    queue_signal_types: Counter[str] = Counter()
    with args.review_queue.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            item = json.loads(line)
            record_id = item.get("record_id")
            group_id = item.get("split_group_id")
            if record_id not in feature_ids or record_id in queue_ids:
                raise ValueError(f"queue line {line_number}: invalid or duplicate record")
            if group_id in queue_groups:
                raise ValueError(f"queue line {line_number}: duplicate split group")
            if item.get("review_status") != "UNREVIEWED":
                raise ValueError(f"queue line {line_number}: queue must remain unreviewed")
            queue_ids.add(record_id)
            queue_groups.add(group_id)
            queue_reasons[str(item.get("queue_reason"))] += 1
            for signal_type in item.get("signal_types", []):
                queue_signal_types[str(signal_type)] += 1

    report = json.loads(args.report.read_text(encoding="utf-8"))
    expected_partitions = {"train": 11344, "validation": 2429}
    if dict(partition_counts) != expected_partitions:
        raise ValueError(f"Unexpected processed partitions: {dict(partition_counts)}")
    if test_count != 2429 or report.get("test_partition_text_processed") != 0:
        raise ValueError("Frozen test partition was not preserved")
    if report.get("processed_record_count") != len(feature_ids):
        raise ValueError("Report processed count mismatch")
    if report.get("candidate_record_count") != candidate_count:
        raise ValueError("Report candidate count mismatch")
    if report.get("review_queue_record_count") != len(queue_ids):
        raise ValueError("Report queue count mismatch")
    if report.get("review_queue_reason_counts") != dict(sorted(queue_reasons.items())):
        raise ValueError("Report queue reason counts mismatch")
    expected_queue_signal_counts = {name: queue_signal_types[name] for name in SIGNAL_TYPES}
    if report.get("review_queue_signal_type_counts") != expected_queue_signal_counts:
        raise ValueError("Report queue signal type counts mismatch")
    if report.get("rule_set_sha256") != rule_set_sha256():
        raise ValueError("Rule-set fingerprint mismatch")
    if report.get("source_labels_used_for_extraction") is not False:
        raise ValueError("Source-label extraction gate is open")
    if report.get("network_operations") != 0 or report.get("raw_files_modified") is not False:
        raise ValueError("Safety contract failed")

    print(
        json.dumps(
            {
                "status": "VALID",
                "feature_record_count": len(feature_ids),
                "candidate_record_count": candidate_count,
                "test_partition_text_processed": 0,
                "review_queue_reason_counts": dict(sorted(queue_reasons.items())),
                "errors": [],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
