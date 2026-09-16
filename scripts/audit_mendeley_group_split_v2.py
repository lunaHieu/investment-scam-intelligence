"""Independently audit structure and residual text similarity in group_split_v2.

This script does not train a classifier. A character TF-IDF space is fitted on
benchmark train text only and is used solely to measure each evaluation row's
nearest-train cosine similarity. Labels and source names are reporting strata,
never predictive inputs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import pairwise_distances_chunked

from build_mendeley_group_split_v2 import (
    ALL_PARTITIONS,
    AUXILIARY_REASON,
    BENCHMARK_PARTITIONS,
    EXPECTED_BENCHMARK_PARTITION_COUNTS,
    EXPECTED_CONFLICT_RECORD_IDS,
    EXPECTED_FAKE_PROFILE_ENTITIES,
    EXPECTED_FAKE_PROFILE_ROWS,
    EXPECTED_QUARANTINE_ROWS,
    EXPECTED_RAW_ROWS,
    GROUPING_RULES,
    QUARANTINE_REASON,
    cross_partition_key_count,
    fake_entity_profile,
)


AUDIT_ID = "MENDELEY_GROUP_SPLIT_V2_AUDIT"
CHAR_MAX_FEATURES = 100_000
SIMILARITY_THRESHOLDS = (0.90, 0.95, 0.99)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "record_id",
            "source_dataset",
            "text_content",
            "label",
            "partition",
            "original_partition",
            "split_group_id",
            "benchmark_eligible",
            "split_exclusion_reason",
            "entity_group_id",
            "entity_post_index",
        }
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"Split CSV must contain {sorted(required)}")
        return list(reader.fieldnames), list(reader)


def nearest_train_cosine(
    train_matrix, evaluation_matrix
) -> tuple[np.ndarray, np.ndarray]:
    similarities: list[np.ndarray] = []
    nearest_indices: list[np.ndarray] = []
    for distances in pairwise_distances_chunked(
        evaluation_matrix,
        train_matrix,
        metric="cosine",
        n_jobs=1,
        working_memory=256,
    ):
        indices = np.argmin(distances, axis=1)
        nearest_indices.append(indices.astype(np.int64, copy=False))
        similarities.append(1.0 - distances[np.arange(len(indices)), indices])
    if not similarities:
        return np.asarray([], dtype=np.float64), np.asarray([], dtype=np.int64)
    return (
        np.clip(np.concatenate(similarities), 0.0, 1.0),
        np.concatenate(nearest_indices),
    )


def summarize(values: np.ndarray) -> dict[str, int | float]:
    if not len(values):
        return {
            "row_count": 0,
            "mean": 0.0,
            "median": 0.0,
            "p95": 0.0,
            "maximum": 0.0,
            **{f"count_gte_{threshold:.2f}".replace(".", "_"): 0 for threshold in SIMILARITY_THRESHOLDS},
        }
    result: dict[str, int | float] = {
        "row_count": int(len(values)),
        "mean": round(float(np.mean(values)), 6),
        "median": round(float(np.median(values)), 6),
        "p95": round(float(np.quantile(values, 0.95)), 6),
        "maximum": round(float(np.max(values)), 6),
    }
    for threshold in SIMILARITY_THRESHOLDS:
        key = f"count_gte_{threshold:.2f}".replace(".", "_")
        result[key] = int(np.sum(values >= threshold))
    return result


def similarity_report(
    values: np.ndarray,
    rows: list[dict[str, str]],
    nearest_indices: np.ndarray,
    train_rows: list[dict[str, str]],
) -> dict:
    by_source = {}
    for source in sorted({row["source_dataset"] for row in rows}):
        indices = np.asarray(
            [index for index, row in enumerate(rows) if row["source_dataset"] == source],
            dtype=np.int64,
        )
        by_source[source] = summarize(values[indices])
    by_label = {}
    for label in sorted({row["label"] for row in rows}):
        indices = np.asarray(
            [index for index, row in enumerate(rows) if row["label"] == label],
            dtype=np.int64,
        )
        by_label[label] = summarize(values[indices])
    ranked = sorted(
        range(len(rows)),
        key=lambda index: (-float(values[index]), rows[index]["record_id"]),
    )[:20]
    return {
        "overall": summarize(values),
        "by_source_dataset": by_source,
        "by_source_label": by_label,
        "highest_similarity_examples": [
            {
                "record_id": rows[index]["record_id"],
                "source_dataset": rows[index]["source_dataset"],
                "source_label": rows[index]["label"],
                "nearest_train_record_id": train_rows[int(nearest_indices[index])]["record_id"],
                "nearest_train_source_dataset": train_rows[int(nearest_indices[index])]["source_dataset"],
                "cosine_similarity": round(float(values[index]), 6),
            }
            for index in ranked
        ],
    }


def structural_audit(rows: list[dict[str, str]]) -> tuple[dict, dict[str, bool]]:
    partition_counts = Counter(row["partition"] for row in rows)
    partitions_by_group: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        partitions_by_group[row["split_group_id"]].add(row["partition"])
    group_crossing = sum(len(values) > 1 for values in partitions_by_group.values())
    cross_keys = {
        rule[0]: cross_partition_key_count(rows, rule) for rule in GROUPING_RULES
    }
    fake_rows = [row for row in rows if row["source_dataset"] == "fake_profile_post"]
    quarantine_rows = [row for row in rows if row["partition"] == "quarantine"]
    benchmark_rows = [row for row in rows if row["partition"] in BENCHMARK_PARTITIONS]
    entity_profile = fake_entity_profile(rows)
    reasons_valid = all(
        (
            row["partition"] in BENCHMARK_PARTITIONS
            and row["benchmark_eligible"] == "1"
            and row["split_exclusion_reason"] == ""
        )
        or (
            row["partition"] == "auxiliary"
            and row["benchmark_eligible"] == "0"
            and row["split_exclusion_reason"] == AUXILIARY_REASON
        )
        or (
            row["partition"] == "quarantine"
            and row["benchmark_eligible"] == "0"
            and row["split_exclusion_reason"] == QUARANTINE_REASON
        )
        for row in rows
    )
    entity_fields_valid = all(
        (
            row["source_dataset"] == "fake_profile_post"
            and bool(row["entity_group_id"])
            and row["entity_post_index"].isdigit()
        )
        or (
            row["source_dataset"] != "fake_profile_post"
            and row["entity_group_id"] == ""
            and row["entity_post_index"] == ""
        )
        for row in rows
    )
    labels_by_group: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        labels_by_group[row["split_group_id"]].add(row["label"])
    conflicting_groups = {
        group_id for group_id, labels in labels_by_group.items() if len(labels) > 1
    }
    quarantine_groups = {row["split_group_id"] for row in quarantine_rows}
    gates = {
        "expected_total_rows": len(rows) == EXPECTED_RAW_ROWS,
        "record_ids_unique": len({row["record_id"] for row in rows}) == len(rows),
        "partitions_valid": set(partition_counts) == set(ALL_PARTITIONS),
        "benchmark_partition_counts_exact": all(
            partition_counts[partition] == count
            for partition, count in EXPECTED_BENCHMARK_PARTITION_COUNTS.items()
        ),
        "auxiliary_count_exact": partition_counts["auxiliary"] == EXPECTED_FAKE_PROFILE_ROWS,
        "quarantine_count_exact": partition_counts["quarantine"] == EXPECTED_QUARANTINE_ROWS,
        "routing_flags_and_reasons_valid": reasons_valid,
        "fake_profile_only_auxiliary": len(fake_rows) == EXPECTED_FAKE_PROFILE_ROWS
        and all(row["partition"] == "auxiliary" for row in fake_rows),
        "entity_fields_valid": entity_fields_valid,
        "fake_entity_count_exact": entity_profile["parsed_entity_count"] == EXPECTED_FAKE_PROFILE_ENTITIES,
        "fake_entities_parse_and_do_not_cross": (
            entity_profile["malformed_record_id_count"] == 0
            and entity_profile["entities_crossing_partitions"] == 0
        ),
        "quarantine_ids_exact": {
            row["record_id"] for row in quarantine_rows
        } == EXPECTED_CONFLICT_RECORD_IDS,
        "every_and_only_conflicting_group_quarantined": conflicting_groups == quarantine_groups,
        "split_groups_do_not_cross_partitions": group_crossing == 0,
        "known_normalized_keys_do_not_cross_partitions": not any(cross_keys.values()),
        "benchmark_has_both_labels": {row["label"] for row in benchmark_rows} == {"0", "1"},
    }
    details = {
        "row_count_by_partition": {
            partition: partition_counts[partition] for partition in ALL_PARTITIONS
        },
        "split_group_count": len(partitions_by_group),
        "split_group_cross_partition_count": group_crossing,
        "grouping_key_cross_partition_counts": cross_keys,
        "conflicting_split_group_count": len(conflicting_groups),
        "quarantine_record_ids": sorted(row["record_id"] for row in quarantine_rows),
        "fake_profile_entity_profile": entity_profile,
    }
    return details, gates


def run_audit(input_path: Path, *, run_at: str) -> dict:
    fieldnames, rows = read_rows(input_path)
    structure, gates = structural_audit(rows)
    failed = sorted(name for name, passed in gates.items() if not passed)
    if failed:
        raise ValueError("Split structural audit failed: " + ", ".join(failed))

    partitions = {
        partition: [row for row in rows if row["partition"] == partition]
        for partition in BENCHMARK_PARTITIONS
    }
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(3, 5),
        min_df=2,
        max_df=0.995,
        max_features=CHAR_MAX_FEATURES,
        sublinear_tf=True,
    )
    train_matrix = vectorizer.fit_transform(
        [row.get("text_content") or "" for row in partitions["train"]]
    ).tocsr()
    similarity = {}
    for partition in ("validation", "test"):
        matrix = vectorizer.transform(
            [row.get("text_content") or "" for row in partitions[partition]]
        ).tocsr()
        values, nearest_indices = nearest_train_cosine(train_matrix, matrix)
        similarity[partition] = similarity_report(
            values, partitions[partition], nearest_indices, partitions["train"]
        )

    return {
        "audit_id": AUDIT_ID,
        "run_at": run_at,
        "status": "FROZEN_DIAGNOSTIC_AUDIT",
        "input": {
            "file_name": input_path.name,
            "sha256": sha256_file(input_path),
            "row_count": len(rows),
            "column_count": len(fieldnames),
        },
        "scope": {
            "classifier_trained": False,
            "labels_used_as_predictive_features": False,
            "source_dataset_used_as_predictive_feature": False,
            "train_fitted_text_space": True,
            "evaluation_text_used_for_vectorizer_fit": False,
            "purpose": "Residual nearest-train text-similarity diagnostic only.",
        },
        "structure": structure,
        "structural_quality_gates": gates,
        "character_similarity_space": {
            "analyzer": "char_wb",
            "ngram_range": [3, 5],
            "lowercase": True,
            "strip_accents": "unicode",
            "min_df": 2,
            "max_df": 0.995,
            "max_features": CHAR_MAX_FEATURES,
            "sublinear_tf": True,
            "metric": "cosine similarity to nearest benchmark-train row",
            "feature_count": int(train_matrix.shape[1]),
            "train_nnz": int(train_matrix.nnz),
        },
        "nearest_train_similarity": similarity,
        "interpretation": {
            "hard_gate": "Known exact and normalized grouping keys must have zero cross-partition groups.",
            "diagnostic_only": (
                "High character cosine similarity is reported, not thresholded as a pass/fail gate; "
                "zero known-template overlap does not prove zero semantic near-duplicates."
            ),
        },
        "safety_contract": {
            "raw_files_modified": False,
            "split_file_modified": False,
            "network_operations": 0,
            "model_training_performed": False,
            "predictions_created": 0,
        },
    }


def write_json(path: Path, value: dict, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing audit: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-at", default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        raise ValueError("Input split and output audit must be different files")
    if args.output.exists() and not args.overwrite:
        raise FileExistsError(f"Refusing to overwrite existing audit: {args.output}")
    run_at = args.run_at or datetime.now(timezone.utc).isoformat()
    report = run_audit(args.input, run_at=run_at)
    write_json(args.output, report, overwrite=args.overwrite)
    print(
        json.dumps(
            {
                "audit_id": report["audit_id"],
                "status": report["status"],
                "input_sha256": report["input"]["sha256"],
                "validation": report["nearest_train_similarity"]["validation"]["overall"],
                "test": report["nearest_train_similarity"]["test"]["overall"],
                "all_structural_quality_gates_passed": all(
                    report["structural_quality_gates"].values()
                ),
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
