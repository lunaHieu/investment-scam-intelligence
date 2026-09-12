"""Build a deterministic leakage-aware Mendeley split without changing raw data."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from audit_mendeley_text_overlap import normalize_surface, normalize_template


SPLITS = ("train", "validation", "test")
TARGET_RATIOS = {"train": 0.70, "validation": 0.15, "test": 0.15}


class DisjointSet:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root == right_root:
            return
        if self.rank[left_root] < self.rank[right_root]:
            left_root, right_root = right_root, left_root
        self.parent[right_root] = left_root
        if self.rank[left_root] == self.rank[right_root]:
            self.rank[left_root] += 1


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"record_id", "source_dataset", "text_content", "label", "partition"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"CSV must contain {sorted(required)}")
        return list(reader.fieldnames), list(reader)


def build_groups(rows: list[dict[str, str]]) -> list[list[int]]:
    dsu = DisjointSet(len(rows))
    for key_fn, minimum_tokens in ((normalize_surface, 1), (normalize_template, 10)):
        first_for_key: dict[str, int] = {}
        for index, row in enumerate(rows):
            key = key_fn(row.get("text_content") or "")
            if len(key.split()) < minimum_tokens:
                continue
            key_hash = sha(key)
            if key_hash in first_for_key:
                dsu.union(first_for_key[key_hash], index)
            else:
                first_for_key[key_hash] = index
    groups: dict[int, list[int]] = defaultdict(list)
    for index in range(len(rows)):
        groups[dsu.find(index)].append(index)
    return list(groups.values())


def assign_groups(rows: list[dict[str, str]], groups: list[list[int]]) -> dict[int, str]:
    strata_total = Counter((row["source_dataset"], row["label"]) for row in rows)
    target_total = {split: len(rows) * TARGET_RATIOS[split] for split in SPLITS}
    target_strata = {
        split: {stratum: count * TARGET_RATIOS[split] for stratum, count in strata_total.items()}
        for split in SPLITS
    }
    current_total = Counter()
    current_strata = {split: Counter() for split in SPLITS}
    assignment: dict[int, str] = {}

    def group_identity(indices: list[int]) -> str:
        ids = sorted(rows[index]["record_id"] for index in indices)
        return sha("\n".join(ids))

    ordered = sorted(groups, key=lambda indices: (-len(indices), group_identity(indices)))
    for indices in ordered:
        counts = Counter((rows[index]["source_dataset"], rows[index]["label"]) for index in indices)
        best_split = None
        best_score = None
        for split in SPLITS:
            global_need = max(target_total[split] - current_total[split], 0.0)
            covered_need = sum(
                min(count, max(target_strata[split][stratum] - current_strata[split][stratum], 0.0))
                for stratum, count in counts.items()
            )
            fill_ratio = current_total[split] / target_total[split] if target_total[split] else 1.0
            score = (covered_need / len(indices), global_need / target_total[split], -fill_ratio)
            if best_score is None or score > best_score:
                best_split, best_score = split, score
        assert best_split is not None
        for index in indices:
            assignment[index] = best_split
        current_total[best_split] += len(indices)
        current_strata[best_split].update(counts)
    return assignment


def cross_split_group_count(rows: list[dict[str, str]], key_fn, minimum_tokens: int) -> int:
    partitions_by_key: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        key = key_fn(row.get("text_content") or "")
        if len(key.split()) >= minimum_tokens:
            partitions_by_key[sha(key)].add(row["partition"])
    return sum(1 for partitions in partitions_by_key.values() if len(partitions) > 1)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    fieldnames, rows = read_csv(args.input)
    groups = build_groups(rows)
    assignment = assign_groups(rows, groups)
    for index, row in enumerate(rows):
        row["original_partition"] = row["partition"]
        row["partition"] = assignment[index]

    for indices in groups:
        group_id = "GRP_" + sha("\n".join(sorted(rows[index]["record_id"] for index in indices)))[:16].upper()
        for index in indices:
            rows[index]["split_group_id"] = group_id

    output_fields = fieldnames + [name for name in ("original_partition", "split_group_id") if name not in fieldnames]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_fields)
        writer.writeheader()
        writer.writerows(rows)

    partition_counts = Counter(row["partition"] for row in rows)
    stratum_counts = {
        split: dict(sorted(Counter(
            f"{row['source_dataset']}|label={row['label']}"
            for row in rows if row["partition"] == split
        ).items()))
        for split in SPLITS
    }
    report = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "input": str(args.input),
        "output": str(args.output),
        "policy": "Duplicate and template-candidate groups are indivisible; deterministic 70/15/15 assignment stratified by source_dataset and label.",
        "row_count": len(rows),
        "group_count": len(groups),
        "largest_group_size": max(map(len, groups)),
        "partition_counts": dict(sorted(partition_counts.items())),
        "partition_ratios": {split: round(partition_counts[split] / len(rows), 6) for split in SPLITS},
        "stratum_counts": stratum_counts,
        "verification": {
            "surface_normalized_cross_split_groups": cross_split_group_count(rows, normalize_surface, 1),
            "template_candidate_cross_split_groups": cross_split_group_count(rows, normalize_template, 10),
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if any(report["verification"].values()):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
