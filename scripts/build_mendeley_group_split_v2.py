"""Build the strict, leakage-aware Mendeley V2 research split.

The pinned raw CSV is never modified. Every raw row is copied to one derived
CSV, while ``partition`` is replaced by one of train/validation/test,
auxiliary, or quarantine. Fake-profile rows are retained as auxiliary data
because their account/template graph cannot be split safely. Mixed-label text
components are retained in quarantine without changing source labels.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from audit_mendeley_text_overlap import (
    normalize_near_template_v2,
    normalize_surface,
    normalize_template,
    normalize_template_v2,
)
from build_mendeley_group_split import DisjointSet


SPLIT_ID = "MENDELEY_GROUP_SPLIT_V2"
SOURCE_ID = "mendeley_investment_deceptive_2026"
SOURCE_VERSION = "2"
EXPECTED_RAW_SHA256 = "a4b336074176efb5746d1981506c1f1faba19a1b0a20f3b9e95dc8be94ea2504"
EXPECTED_RAW_ROWS = 16_202
EXPECTED_RAW_COLUMNS = 32
EXPECTED_FAKE_PROFILE_ROWS = 10_607
EXPECTED_FAKE_PROFILE_ENTITIES = 1_387
EXPECTED_QUARANTINE_ROWS = 3
EXPECTED_BENCHMARK_ROWS = 5_592
EXPECTED_BENCHMARK_SOURCES = {
    "cresci_stock_2018",
    "phishing",
    "spam_email",
    "twitter_bot_detection",
}
EXPECTED_RAW_SOURCES = EXPECTED_BENCHMARK_SOURCES | {"fake_profile_post"}
EXPECTED_CONFLICT_RECORD_IDS = {"phishing_5164", "phishing_5168", "phishing_14168"}
EXPECTED_BENCHMARK_PARTITION_COUNTS = {
    "train": 3_916,
    "validation": 838,
    "test": 838,
}

BENCHMARK_PARTITIONS = ("train", "validation", "test")
ALL_PARTITIONS = BENCHMARK_PARTITIONS + ("auxiliary", "quarantine")
TARGET_RATIOS = {"train": 0.70, "validation": 0.15, "test": 0.15}
AUXILIARY_REASON = "entity_template_graph_not_splittable_without_leakage"
QUARANTINE_REASON = "conflicting_labels_within_duplicate_template_group"
DERIVED_FIELDS = (
    "original_partition",
    "split_group_id",
    "benchmark_eligible",
    "split_exclusion_reason",
    "entity_group_id",
    "entity_post_index",
)
FAKE_ENTITY_RE = re.compile(
    r"^fake_profile_post_(?P<account>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-"
    r"[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12})_"
    r"(?P<post_index>[0-9]+)$"
)
ENTITY_METADATA_FIELDS = (
    "has_metadata",
    "followers",
    "friends_following",
    "statuses_posts",
    "account_age_days",
    "verified_bool",
    "has_bio",
    "has_location",
    "has_url",
    "is_private",
    "default_profile_image_flag",
)

GroupingRule = tuple[str, Callable[[str], str], int]
GROUPING_RULES: tuple[GroupingRule, ...] = (
    ("surface_normalized", normalize_surface, 1),
    ("legacy_template", normalize_template, 10),
    ("near_template_v2", normalize_near_template_v2, 1),
    ("template_v2", normalize_template_v2, 10),
)


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"record_id", "source_dataset", "text_content", "label", "partition"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"CSV must contain {sorted(required)}")
        return list(reader.fieldnames), list(reader)


def validate_paths(input_path: Path, output_path: Path, report_path: Path) -> None:
    resolved = [path.resolve() for path in (input_path, output_path, report_path)]
    if len(set(resolved)) != 3:
        raise ValueError("Input, output CSV, and report must be three different files")


def validate_raw_contract(
    path: Path,
    fieldnames: list[str],
    rows: list[dict[str, str]],
    *,
    require_pinned_hash: bool = True,
) -> str:
    if any(field in fieldnames for field in DERIVED_FIELDS):
        raise ValueError("Input already contains derived split fields; use the immutable raw CSV")
    raw_hash = sha256_file(path)
    if require_pinned_hash and raw_hash != EXPECTED_RAW_SHA256:
        raise ValueError(f"Pinned raw SHA-256 mismatch: {raw_hash}")
    if require_pinned_hash and len(fieldnames) != EXPECTED_RAW_COLUMNS:
        raise ValueError(f"Expected {EXPECTED_RAW_COLUMNS} raw columns, found {len(fieldnames)}")
    if require_pinned_hash and len(rows) != EXPECTED_RAW_ROWS:
        raise ValueError(f"Expected {EXPECTED_RAW_ROWS} raw rows, found {len(rows)}")
    record_ids = [row["record_id"] for row in rows]
    if not all(record_ids) or len(record_ids) != len(set(record_ids)):
        raise ValueError("record_id must be present and unique for every raw row")
    invalid_labels = sorted({row["label"] for row in rows} - {"0", "1"})
    if invalid_labels:
        raise ValueError(f"Unexpected source labels: {invalid_labels}")
    invalid_partitions = sorted(
        {row["partition"] for row in rows} - set(BENCHMARK_PARTITIONS)
    )
    if invalid_partitions:
        raise ValueError(f"Unexpected raw partition values: {invalid_partitions}")
    if require_pinned_hash and {row["source_dataset"] for row in rows} != EXPECTED_RAW_SOURCES:
        raise ValueError("Pinned raw source_dataset whitelist does not match")
    return raw_hash


def key_is_eligible(key: str, minimum_tokens: int) -> bool:
    return bool(key) and len(key.split()) >= minimum_tokens


def grouping_rule_profile(
    rows: list[dict[str, str]], rule: GroupingRule
) -> dict[str, int | str]:
    name, key_fn, minimum_tokens = rule
    counts: Counter[str] = Counter()
    for row in rows:
        key = key_fn(row.get("text_content") or "")
        if key_is_eligible(key, minimum_tokens):
            counts[key] += 1
    repeated = [count for count in counts.values() if count > 1]
    return {
        "name": name,
        "minimum_tokens": minimum_tokens,
        "eligible_rows": sum(counts.values()),
        "unique_keys": len(counts),
        "repeated_keys": len(repeated),
        "rows_in_repeated_keys": sum(repeated),
        "largest_key_rows": max(counts.values(), default=0),
    }


def build_groups(rows: list[dict[str, str]]) -> list[list[int]]:
    dsu = DisjointSet(len(rows))
    for _, key_fn, minimum_tokens in GROUPING_RULES:
        first_for_key: dict[str, int] = {}
        for index, row in enumerate(rows):
            key = key_fn(row.get("text_content") or "")
            if not key_is_eligible(key, minimum_tokens):
                continue
            if key in first_for_key:
                dsu.union(first_for_key[key], index)
            else:
                first_for_key[key] = index
    components: dict[int, list[int]] = defaultdict(list)
    for index in range(len(rows)):
        components[dsu.find(index)].append(index)
    return sorted(components.values(), key=lambda indices: group_identity(rows, indices))


def group_identity(rows: list[dict[str, str]], indices: list[int]) -> str:
    return sha("\n".join(sorted(rows[index]["record_id"] for index in indices)))


def split_group_id(rows: list[dict[str, str]], indices: list[int]) -> str:
    return "GRP2_" + group_identity(rows, indices)[:16].upper()


def classify_groups(
    rows: list[dict[str, str]], groups: list[list[int]]
) -> tuple[list[list[int]], dict[int, str], dict[int, str]]:
    eligible_groups: list[list[int]] = []
    fixed_partition: dict[int, str] = {}
    exclusion_reason: dict[int, str] = {}
    for indices in groups:
        sources = {rows[index]["source_dataset"] for index in indices}
        if len(sources) != 1:
            ids = [rows[index]["record_id"] for index in indices[:10]]
            raise ValueError(f"Text component mixes source datasets: {ids}")
        labels = {rows[index]["label"] for index in indices}
        if sources == {"fake_profile_post"}:
            for index in indices:
                fixed_partition[index] = "auxiliary"
                exclusion_reason[index] = AUXILIARY_REASON
        elif len(labels) > 1:
            for index in indices:
                fixed_partition[index] = "quarantine"
                exclusion_reason[index] = QUARANTINE_REASON
        else:
            eligible_groups.append(indices)
    return eligible_groups, fixed_partition, exclusion_reason


def assign_groups(
    rows: list[dict[str, str]], groups: list[list[int]]
) -> dict[int, str]:
    """Assign homogeneous eligible groups using deterministic V1-compatible greedy."""

    eligible_indices = [index for indices in groups for index in indices]
    strata_total = Counter(
        (rows[index]["source_dataset"], rows[index]["label"])
        for index in eligible_indices
    )
    target_total = {
        split: len(eligible_indices) * TARGET_RATIOS[split]
        for split in BENCHMARK_PARTITIONS
    }
    target_strata = {
        split: {
            stratum: count * TARGET_RATIOS[split]
            for stratum, count in strata_total.items()
        }
        for split in BENCHMARK_PARTITIONS
    }
    current_total: Counter[str] = Counter()
    current_strata = {split: Counter() for split in BENCHMARK_PARTITIONS}
    assignment: dict[int, str] = {}

    ordered = sorted(
        groups,
        key=lambda indices: (-len(indices), group_identity(rows, indices)),
    )
    for indices in ordered:
        counts = Counter(
            (rows[index]["source_dataset"], rows[index]["label"])
            for index in indices
        )
        if len(counts) != 1:
            raise ValueError("Benchmark component must contain exactly one source-label stratum")
        best_split = None
        best_score = None
        for split in BENCHMARK_PARTITIONS:
            global_need = max(target_total[split] - current_total[split], 0.0)
            covered_need = sum(
                min(
                    count,
                    max(
                        target_strata[split][stratum]
                        - current_strata[split][stratum],
                        0.0,
                    ),
                )
                for stratum, count in counts.items()
            )
            fill_ratio = (
                current_total[split] / target_total[split]
                if target_total[split]
                else 1.0
            )
            score = (
                covered_need / len(indices),
                global_need / target_total[split],
                -fill_ratio,
            )
            if best_score is None or score > best_score:
                best_split, best_score = split, score
        assert best_split is not None
        for index in indices:
            assignment[index] = best_split
        current_total[best_split] += len(indices)
        current_strata[best_split].update(counts)
    return assignment


def parse_fake_entity(record_id: str) -> tuple[str, int] | None:
    match = FAKE_ENTITY_RE.fullmatch(record_id)
    if not match:
        return None
    account = str(uuid.UUID(match.group("account"))).lower()
    return account, int(match.group("post_index"))


def parse_fake_entity_id(record_id: str) -> str | None:
    parsed = parse_fake_entity(record_id)
    return parsed[0] if parsed else None


def fake_entity_profile(rows: list[dict[str, str]]) -> dict[str, int]:
    fake_rows = [row for row in rows if row["source_dataset"] == "fake_profile_post"]
    entities: dict[str, list[dict[str, str]]] = defaultdict(list)
    entity_indices: set[tuple[str, int]] = set()
    duplicate_entity_indices = 0
    post_indices: list[int] = []
    malformed = 0
    for row in fake_rows:
        parsed = parse_fake_entity(row["record_id"])
        if parsed is None:
            malformed += 1
        else:
            entity_id, post_index = parsed
            entities[entity_id].append(row)
            if (entity_id, post_index) in entity_indices:
                duplicate_entity_indices += 1
            entity_indices.add((entity_id, post_index))
            post_indices.append(post_index)
    metadata_conflicts = 0
    for entity_rows in entities.values():
        signatures = {
            tuple(row.get(field, "") for field in ENTITY_METADATA_FIELDS)
            for row in entity_rows
        }
        metadata_conflicts += len(signatures) > 1
    partitions_crossed = sum(
        len({row["partition"] for row in entity_rows}) > 1
        for entity_rows in entities.values()
    )
    mixed_label_entities = sum(
        len({row["label"] for row in entity_rows}) > 1
        for entity_rows in entities.values()
    )
    entity_sizes = [len(entity_rows) for entity_rows in entities.values()]
    return {
        "row_count": len(fake_rows),
        "parsed_entity_count": len(entities),
        "malformed_record_id_count": malformed,
        "duplicate_entity_post_index_count": duplicate_entity_indices,
        "minimum_post_index": min(post_indices, default=None),
        "maximum_post_index": max(post_indices, default=None),
        "minimum_posts_per_entity": min(entity_sizes, default=0),
        "maximum_posts_per_entity": max(entity_sizes, default=0),
        "entities_with_mixed_labels": mixed_label_entities,
        "entities_with_metadata_conflict": metadata_conflicts,
        "entities_crossing_partitions": partitions_crossed,
    }


def materialize_rows(
    source_rows: list[dict[str, str]],
    groups: list[list[int]],
    benchmark_assignment: dict[int, str],
    fixed_partition: dict[int, str],
    exclusion_reason: dict[int, str],
) -> list[dict[str, str]]:
    group_ids = {
        index: split_group_id(source_rows, indices)
        for indices in groups
        for index in indices
    }
    if len(set(group_ids.values())) != len(groups):
        raise ValueError("Truncated split_group_id collision detected")
    output_rows: list[dict[str, str]] = []
    for index, source in enumerate(source_rows):
        partition = benchmark_assignment.get(index, fixed_partition.get(index))
        if partition not in ALL_PARTITIONS:
            raise ValueError(f"No valid assignment for row {source['record_id']}")
        row = dict(source)
        row["original_partition"] = source["partition"]
        row["partition"] = partition
        row["split_group_id"] = group_ids[index]
        row["benchmark_eligible"] = "1" if partition in BENCHMARK_PARTITIONS else "0"
        row["split_exclusion_reason"] = exclusion_reason.get(index, "")
        parsed_entity = (
            parse_fake_entity(source["record_id"])
            if source["source_dataset"] == "fake_profile_post"
            else None
        )
        row["entity_group_id"] = parsed_entity[0] if parsed_entity else ""
        row["entity_post_index"] = str(parsed_entity[1]) if parsed_entity else ""
        output_rows.append(row)
    return output_rows


def cross_partition_key_count(
    rows: list[dict[str, str]], rule: GroupingRule
) -> int:
    _, key_fn, minimum_tokens = rule
    partitions_by_key: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        key = key_fn(row.get("text_content") or "")
        if key_is_eligible(key, minimum_tokens):
            partitions_by_key[key].add(row["partition"])
    return sum(1 for partitions in partitions_by_key.values() if len(partitions) > 1)


def nested_source_label_counts(
    rows: list[dict[str, str]], partitions: tuple[str, ...] = ALL_PARTITIONS
) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for partition in partitions:
        counts = Counter(
            f"{row['source_dataset']}|label={row['label']}"
            for row in rows
            if row["partition"] == partition
        )
        result[partition] = dict(sorted(counts.items()))
    return result


def build_quality_report(
    raw_rows: list[dict[str, str]],
    output_rows: list[dict[str, str]],
    groups: list[list[int]],
    eligible_groups: list[list[int]],
) -> tuple[dict[str, object], dict[str, bool]]:
    partition_counts = Counter(row["partition"] for row in output_rows)
    partition_group_counts = {
        partition: len(
            {row["split_group_id"] for row in output_rows if row["partition"] == partition}
        )
        for partition in ALL_PARTITIONS
    }
    benchmark_rows = [
        row for row in output_rows if row["partition"] in BENCHMARK_PARTITIONS
    ]
    benchmark_count = len(benchmark_rows)
    benchmark_strata = Counter(
        (row["source_dataset"], row["label"]) for row in benchmark_rows
    )
    split_strata = {
        partition: Counter(
            (row["source_dataset"], row["label"])
            for row in benchmark_rows
            if row["partition"] == partition
        )
        for partition in BENCHMARK_PARTITIONS
    }
    split_group_strata = {
        partition: Counter(
            (row["source_dataset"], row["label"])
            for group in eligible_groups
            if output_rows[group[0]]["partition"] == partition
            for row in [output_rows[group[0]]]
        )
        for partition in BENCHMARK_PARTITIONS
    }
    eligible_group_strata = Counter(
        (raw_rows[group[0]]["source_dataset"], raw_rows[group[0]]["label"])
        for group in eligible_groups
    )
    partition_ratios = {
        partition: partition_counts[partition] / benchmark_count
        for partition in BENCHMARK_PARTITIONS
    }
    max_partition_deviation = max(
        abs(partition_ratios[partition] - TARGET_RATIOS[partition])
        for partition in BENCHMARK_PARTITIONS
    )
    stratum_deviations = []
    for partition in BENCHMARK_PARTITIONS:
        for stratum, total in benchmark_strata.items():
            stratum_deviations.append(
                abs(split_strata[partition][stratum] / total - TARGET_RATIOS[partition])
            )
    max_stratum_deviation = max(stratum_deviations, default=0.0)
    split_group_crossing = 0
    partitions_by_group: dict[str, set[str]] = defaultdict(set)
    for row in output_rows:
        partitions_by_group[row["split_group_id"]].add(row["partition"])
    split_group_crossing = sum(
        len(partitions) > 1 for partitions in partitions_by_group.values()
    )
    cross_key_counts = {
        rule[0]: cross_partition_key_count(output_rows, rule) for rule in GROUPING_RULES
    }
    conflict_ids = {
        row["record_id"] for row in output_rows if row["partition"] == "quarantine"
    }
    fake_rows = [
        row for row in output_rows if row["source_dataset"] == "fake_profile_post"
    ]
    fake_entities = fake_entity_profile(output_rows)
    preserved = all(
        all(
            output.get(field, "") == raw.get(field, "")
            for field in raw
            if field != "partition"
        )
        and output["original_partition"] == raw["partition"]
        and output["label"] == raw["label"]
        for raw, output in zip(raw_rows, output_rows)
    )
    all_strata_present = all(
        set(split_strata[partition]) == set(benchmark_strata)
        for partition in BENCHMARK_PARTITIONS
    )
    minimum_eval_rows = min(
        split_strata[partition][stratum]
        for partition in ("validation", "test")
        for stratum in benchmark_strata
    )
    diversity_strata = [
        stratum for stratum, count in eligible_group_strata.items() if count >= 40
    ]
    minimum_eval_groups = min(
        split_group_strata[partition][stratum]
        for partition in ("validation", "test")
        for stratum in diversity_strata
    )
    source_counts = Counter(row["source_dataset"] for row in benchmark_rows)
    movement = Counter(
        (raw["partition"], output["partition"])
        for raw, output in zip(raw_rows, output_rows)
    )

    gates = {
        "raw_row_order_and_values_preserved": preserved,
        "all_record_ids_unique_and_retained": (
            [row["record_id"] for row in output_rows]
            == [row["record_id"] for row in raw_rows]
            and len({row["record_id"] for row in output_rows}) == len(raw_rows)
        ),
        "expected_total_row_count": len(output_rows) == EXPECTED_RAW_ROWS,
        "expected_benchmark_row_count": benchmark_count == EXPECTED_BENCHMARK_ROWS,
        "expected_benchmark_partition_counts": all(
            partition_counts[partition] == expected
            for partition, expected in EXPECTED_BENCHMARK_PARTITION_COUNTS.items()
        ),
        "expected_auxiliary_row_count": partition_counts["auxiliary"] == EXPECTED_FAKE_PROFILE_ROWS,
        "expected_quarantine_row_count": partition_counts["quarantine"] == EXPECTED_QUARANTINE_ROWS,
        "expected_benchmark_sources": set(source_counts) == EXPECTED_BENCHMARK_SOURCES,
        "expected_conflict_record_ids": conflict_ids == EXPECTED_CONFLICT_RECORD_IDS,
        "fake_profile_only_auxiliary": bool(fake_rows)
        and all(row["partition"] == "auxiliary" for row in fake_rows),
        "fake_profile_entity_ids_all_parse": fake_entities["malformed_record_id_count"] == 0,
        "expected_fake_profile_entity_count": (
            fake_entities["parsed_entity_count"] == EXPECTED_FAKE_PROFILE_ENTITIES
        ),
        "fake_profile_entity_metadata_consistent": (
            fake_entities["entities_with_metadata_conflict"] == 0
        ),
        "fake_profile_entity_post_indices_unique": (
            fake_entities["duplicate_entity_post_index_count"] == 0
        ),
        "fake_profile_entities_have_single_label": (
            fake_entities["entities_with_mixed_labels"] == 0
        ),
        "fake_profile_entities_do_not_cross_partitions": (
            fake_entities["entities_crossing_partitions"] == 0
        ),
        "no_split_group_crosses_partition": split_group_crossing == 0,
        "no_grouping_key_crosses_partition": not any(cross_key_counts.values()),
        "partition_ratio_deviation_within_0_25pp": max_partition_deviation <= 0.0025,
        "source_label_ratio_deviation_within_1pp": max_stratum_deviation <= 0.01,
        "all_source_label_strata_in_all_benchmark_partitions": all_strata_present,
        "minimum_30_rows_per_eval_stratum": minimum_eval_rows >= 30,
        "minimum_10_groups_per_eval_stratum": minimum_eval_groups >= 10,
        "no_source_label_auto_relabeling": all(
            raw["label"] == output["label"] for raw, output in zip(raw_rows, output_rows)
        ),
    }
    details: dict[str, object] = {
        "row_count_by_partition": {
            partition: partition_counts[partition] for partition in ALL_PARTITIONS
        },
        "group_count_by_partition": partition_group_counts,
        "benchmark_partition_ratios": {
            partition: round(value, 8) for partition, value in partition_ratios.items()
        },
        "maximum_partition_ratio_deviation": round(max_partition_deviation, 8),
        "maximum_source_label_ratio_deviation": round(max_stratum_deviation, 8),
        "minimum_evaluation_rows_per_source_label_stratum": minimum_eval_rows,
        "minimum_evaluation_groups_per_source_label_stratum": minimum_eval_groups,
        "source_label_counts_by_partition": nested_source_label_counts(output_rows),
        "original_to_new_partition_movement": {
            f"{original}->{new}": count
            for (original, new), count in sorted(movement.items())
        },
        "benchmark_source_counts": dict(sorted(source_counts.items())),
        "text_component_count": len(groups),
        "largest_text_component_rows": max(map(len, groups), default=0),
        "benchmark_component_count": len(eligible_groups),
        "largest_benchmark_component_rows": max(map(len, eligible_groups), default=0),
        "split_group_cross_partition_count": split_group_crossing,
        "grouping_key_cross_partition_counts": cross_key_counts,
        "quarantine_record_ids": sorted(conflict_ids),
        "fake_profile_entity_profile": fake_entities,
    }
    return details, gates


def write_csv(
    path: Path,
    fieldnames: list[str],
    rows: list[dict[str, str]],
    *,
    overwrite: bool,
) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: dict, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing report: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_split(
    input_path: Path,
    output_path: Path,
    report_path: Path,
    *,
    run_at: str,
    overwrite: bool = False,
) -> dict:
    validate_paths(input_path, output_path, report_path)
    if not input_path.is_file():
        raise FileNotFoundError(input_path)
    if (output_path.exists() or report_path.exists()) and not overwrite:
        existing = output_path if output_path.exists() else report_path
        raise FileExistsError(f"Refusing to overwrite existing artifact: {existing}")
    fieldnames, raw_rows = read_csv(input_path)
    raw_hash_before = validate_raw_contract(input_path, fieldnames, raw_rows)
    groups = build_groups(raw_rows)
    eligible_groups, fixed_partition, exclusion_reason = classify_groups(raw_rows, groups)
    benchmark_assignment = assign_groups(raw_rows, eligible_groups)
    output_rows = materialize_rows(
        raw_rows,
        groups,
        benchmark_assignment,
        fixed_partition,
        exclusion_reason,
    )
    quality, gates = build_quality_report(raw_rows, output_rows, groups, eligible_groups)
    raw_hash_after = sha256_file(input_path)
    gates["raw_sha256_unchanged_during_build"] = raw_hash_before == raw_hash_after
    gates["raw_sha256_matches_pinned_manifest"] = raw_hash_before == EXPECTED_RAW_SHA256
    failed = sorted(name for name, passed in gates.items() if not passed)
    if failed:
        raise ValueError("Strict split quality gates failed: " + ", ".join(failed))

    output_fields = fieldnames + [field for field in DERIVED_FIELDS if field not in fieldnames]
    write_csv(output_path, output_fields, output_rows, overwrite=overwrite)
    output_hash = sha256_file(output_path)
    report = {
        "split_id": SPLIT_ID,
        "run_at": run_at,
        "status": "FROZEN_DERIVED_SPLIT",
        "label_semantics": (
            "Mendeley V2 harmonized deceptive/suspicious source label; not verified "
            "investment-scam ground truth"
        ),
        "input": {
            "source_id": SOURCE_ID,
            "source_version": SOURCE_VERSION,
            "file_name": input_path.name,
            "sha256": raw_hash_before,
            "row_count": len(raw_rows),
            "column_count": len(fieldnames),
        },
        "output": {
            "file_name": output_path.name,
            "sha256": output_hash,
            "row_count": len(output_rows),
            "column_count": len(output_fields),
        },
        "policy": {
            "benchmark_target_ratios": TARGET_RATIOS,
            "benchmark_sources": sorted(EXPECTED_BENCHMARK_SOURCES),
            "grouping_rules": [grouping_rule_profile(raw_rows, rule) for rule in GROUPING_RULES],
            "group_union": "Transitive union across every eligible key from all four grouping rules.",
            "split_group_id": "GRP2_ plus the first 16 uppercase hex characters of SHA-256 over sorted record_id membership.",
            "allocator": (
                "Deterministic largest-component-first greedy assignment, stratified by "
                "source_dataset and source label; SHA-256 record-set identity is the tie-break."
            ),
            "auxiliary": {
                "source_dataset": "fake_profile_post",
                "reason": AUXILIARY_REASON,
            },
            "quarantine": {
                "rule": "Any text component containing more than one source label.",
                "reason": QUARANTINE_REASON,
                "source_labels_preserved": True,
            },
            "not_external_or_gold": True,
            "test_status": (
                "Internal research test created after group_split_v1 results were inspected; "
                "it is not an unopened external or Gold test."
            ),
        },
        "quality": quality,
        "quality_gates": gates,
        "safety_contract": {
            "raw_files_modified": False,
            "network_operations": 0,
            "source_labels_changed": 0,
            "model_training_performed": False,
            "all_raw_rows_retained_in_derived_output": True,
        },
        "limitations": [
            "The grouping rules control known exact/normalized templates; they cannot prove that every semantic near-duplicate was removed.",
            "Auxiliary and quarantine rows are excluded from benchmark fitting, selection, and scoring.",
            "This split is an internal research benchmark, not independent real-world validation.",
        ],
    }
    write_json(report_path, report, overwrite=overwrite)
    if sha256_file(input_path) != raw_hash_before:
        raise RuntimeError("Raw input changed after artifact writing")
    return report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--run-at",
        default=None,
        help="Fixed ISO-8601 timestamp for exact reproduction (default: current UTC).",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    run_at = args.run_at or datetime.now(timezone.utc).isoformat()
    report = build_split(
        args.input,
        args.output,
        args.report,
        run_at=run_at,
        overwrite=args.overwrite,
    )
    print(
        json.dumps(
            {
                "split_id": report["split_id"],
                "status": report["status"],
                "output": str(args.output),
                "report": str(args.report),
                "output_sha256": report["output"]["sha256"],
                "row_count_by_partition": report["quality"]["row_count_by_partition"],
                "all_quality_gates_passed": all(report["quality_gates"].values()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
