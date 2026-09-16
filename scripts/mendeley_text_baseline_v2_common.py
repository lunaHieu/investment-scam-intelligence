"""Shared contracts for the strict Mendeley text baseline V2 workflow."""

from __future__ import annotations

import csv
import hashlib
import json
import statistics
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)


MODEL_ID = "ISI_TEXT_BASELINE_V2"
SELECTION_ID = "MENDELEY_TEXT_BASELINE_V2_VALIDATION_SELECTION"
EXPECTED_SPLIT_SHA256 = "98f75387a4a598d85a6f721d10808979bda694dad8f85354d595679bdd96e734"
EXPECTED_PARTITION_COUNTS = {
    "train": 3_916,
    "validation": 838,
    "test": 838,
    "auxiliary": 10_607,
    "quarantine": 3,
}
BENCHMARK_PARTITIONS = ("train", "validation", "test")
EXCLUDED_PARTITIONS = ("auxiliary", "quarantine")
EXPECTED_SOURCES = {
    "cresci_stock_2018",
    "phishing",
    "spam_email",
    "twitter_bot_detection",
}
LABEL_SEMANTICS = (
    "Mendeley V2 harmonized deceptive/suspicious source label; not verified "
    "investment-scam ground truth"
)
RANDOM_STATE = 20260916
THRESHOLD = 0.5
VECTORIZER_CONFIG = {
    "analyzer": "word",
    "lowercase": True,
    "strip_accents": "unicode",
    "ngram_range": [1, 2],
    "min_df": 2,
    "max_df": 0.995,
    "max_features": 100_000,
    "sublinear_tf": True,
}
CANDIDATES = tuple(
    {"C": c_value, "class_weight": class_weight}
    for class_weight in (None, "balanced")
    for c_value in (0.25, 0.5, 1.0, 2.0, 4.0)
)
SELECTION_POLICY = {
    "primary_metric": "unweighted mean of per-source validation Macro-F1",
    "tie_breakers": [
        "worst-source validation Macro-F1",
        "pooled validation Macro-F1",
        "pooled validation balanced accuracy",
        "earlier predeclared candidate",
    ],
    "threshold": THRESHOLD,
    "test_used_for_selection": False,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_header(fieldnames: list[str] | None) -> None:
    required = {
        "record_id",
        "source_dataset",
        "text_content",
        "label",
        "partition",
        "split_group_id",
        "benchmark_eligible",
        "split_exclusion_reason",
    }
    if fieldnames is None or not required.issubset(fieldnames):
        raise ValueError(f"Split CSV must contain {sorted(required)}")


def _validate_routing_row(
    row: dict[str, str], *, validate_benchmark_label: bool = True
) -> None:
    partition = row["partition"]
    if partition in BENCHMARK_PARTITIONS:
        if row["benchmark_eligible"] != "1" or row["split_exclusion_reason"]:
            raise ValueError(f"Benchmark routing fields invalid: {row['record_id']}")
        if validate_benchmark_label and row["label"] not in {"0", "1"}:
            raise ValueError(f"Benchmark label invalid: {row['record_id']}")
        if row["source_dataset"] not in EXPECTED_SOURCES:
            raise ValueError(f"Unexpected benchmark source: {row['record_id']}")
    elif partition in EXCLUDED_PARTITIONS:
        if row["benchmark_eligible"] != "0" or not row["split_exclusion_reason"]:
            raise ValueError(f"Excluded routing fields invalid: {row['record_id']}")
    else:
        raise ValueError(f"Unexpected partition: {partition}")


def read_selection_data(
    path: Path, *, require_frozen_hash: bool = True, expected_counts: dict | None = None
) -> tuple[dict[str, list[dict[str, str]]], dict]:
    """Load only train/validation records; scan but never retain test/excluded rows."""

    if require_frozen_hash and sha256_file(path) != EXPECTED_SPLIT_SHA256:
        raise ValueError("group_split_v2 SHA-256 does not match the frozen split")
    expected = expected_counts or EXPECTED_PARTITION_COUNTS
    loaded = {"train": [], "validation": []}
    counts: Counter[str] = Counter()
    loaded_groups = {"train": set(), "validation": set()}
    record_ids = set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        _validate_header(reader.fieldnames)
        for row in reader:
            record_id = row["record_id"]
            if record_id in record_ids:
                raise ValueError(f"Duplicate record_id: {record_id}")
            record_ids.add(record_id)
            partition = row["partition"]
            _validate_routing_row(
                row, validate_benchmark_label=partition in loaded
            )
            counts[partition] += 1
            if partition in loaded:
                loaded[partition].append(row)
                loaded_groups[partition].add(row["split_group_id"])
    if dict(counts) != expected:
        raise ValueError(f"Partition counts mismatch: {dict(counts)}")
    if loaded_groups["train"] & loaded_groups["validation"]:
        raise ValueError("split_group_id crosses train and validation")
    for partition, rows in loaded.items():
        if len(rows) != expected[partition]:
            raise ValueError(f"Loaded {partition} row count mismatch")
    return loaded, {
        "partition_counts_scanned": {
            partition: counts[partition] for partition in expected
        },
        "loaded_text_rows": {
            "train": len(loaded["train"]),
            "validation": len(loaded["validation"]),
            "test": 0,
            "auxiliary": 0,
            "quarantine": 0,
        },
        "test_text_transformed": 0,
        "test_labels_used": 0,
        "excluded_rows_used": 0,
    }


def read_final_data(
    path: Path, *, require_frozen_hash: bool = True, expected_counts: dict | None = None
) -> tuple[dict[str, list[dict[str, str]]], dict]:
    """Load benchmark rows only after a frozen selection has been verified."""

    if require_frozen_hash and sha256_file(path) != EXPECTED_SPLIT_SHA256:
        raise ValueError("group_split_v2 SHA-256 does not match the frozen split")
    expected = expected_counts or EXPECTED_PARTITION_COUNTS
    loaded = {partition: [] for partition in BENCHMARK_PARTITIONS}
    counts: Counter[str] = Counter()
    groups_by_partition = {partition: set() for partition in BENCHMARK_PARTITIONS}
    record_ids = set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        _validate_header(reader.fieldnames)
        for row in reader:
            record_id = row["record_id"]
            if record_id in record_ids:
                raise ValueError(f"Duplicate record_id: {record_id}")
            record_ids.add(record_id)
            _validate_routing_row(row)
            partition = row["partition"]
            counts[partition] += 1
            if partition in loaded:
                loaded[partition].append(row)
                groups_by_partition[partition].add(row["split_group_id"])
    if dict(counts) != expected:
        raise ValueError(f"Partition counts mismatch: {dict(counts)}")
    for left_index, left in enumerate(BENCHMARK_PARTITIONS):
        for right in BENCHMARK_PARTITIONS[left_index + 1 :]:
            if groups_by_partition[left] & groups_by_partition[right]:
                raise ValueError(f"split_group_id crosses {left} and {right}")
    return loaded, {
        "partition_counts_scanned": {
            partition: counts[partition] for partition in expected
        },
        "loaded_benchmark_rows": {
            partition: len(loaded[partition]) for partition in BENCHMARK_PARTITIONS
        },
        "auxiliary_rows_loaded_for_modeling": 0,
        "quarantine_rows_loaded_for_modeling": 0,
    }


def texts(rows: list[dict[str, str]]) -> list[str]:
    return [row.get("text_content") or "" for row in rows]


def labels(rows: list[dict[str, str]]) -> np.ndarray:
    return np.asarray([int(row["label"]) for row in rows], dtype=np.int64)


def make_vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(
        analyzer="word",
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.995,
        max_features=100_000,
        sublinear_tf=True,
    )


def make_classifier(config: dict) -> LogisticRegression:
    return LogisticRegression(
        C=float(config["C"]),
        class_weight=config["class_weight"],
        solver="liblinear",
        max_iter=2_000,
        random_state=RANDOM_STATE,
    )


def fit_classifier(classifier: LogisticRegression, matrix, truth: np.ndarray) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        classifier.fit(matrix, truth)


def binary_metrics(
    truth: np.ndarray, predictions: np.ndarray, probabilities: np.ndarray
) -> dict:
    tn, fp, fn, tp = confusion_matrix(truth, predictions, labels=[0, 1]).ravel()
    precision, recall, f1, support = precision_recall_fscore_support(
        truth,
        predictions,
        labels=[0, 1],
        zero_division=0,
    )
    return {
        "row_count": int(len(truth)),
        "threshold_label_1": THRESHOLD,
        "confusion_matrix": {
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp),
        },
        "accuracy": round(float(accuracy_score(truth, predictions)), 6),
        "balanced_accuracy": round(float(balanced_accuracy_score(truth, predictions)), 6),
        "macro_f1": round(float(np.mean(f1)), 6),
        "roc_auc": round(float(roc_auc_score(truth, probabilities)), 6),
        "average_precision": round(float(average_precision_score(truth, probabilities)), 6),
        "per_label": {
            str(label): {
                "precision": round(float(precision[label]), 6),
                "recall": round(float(recall[label]), 6),
                "f1": round(float(f1[label]), 6),
                "support": int(support[label]),
            }
            for label in (0, 1)
        },
    }


def evaluate_classifier(classifier, matrix, rows: list[dict[str, str]]) -> tuple[dict, np.ndarray, np.ndarray]:
    probabilities = classifier.predict_proba(matrix)[:, 1]
    predictions = (probabilities >= THRESHOLD).astype(np.int64)
    return binary_metrics(labels(rows), predictions, probabilities), predictions, probabilities


def evaluate_by_source(
    rows: list[dict[str, str]], predictions: np.ndarray, probabilities: np.ndarray
) -> dict[str, dict]:
    result = {}
    for source in sorted({row["source_dataset"] for row in rows}):
        indices = np.asarray(
            [index for index, row in enumerate(rows) if row["source_dataset"] == source],
            dtype=np.int64,
        )
        result[source] = binary_metrics(
            labels([rows[int(index)] for index in indices]),
            predictions[indices],
            probabilities[indices],
        )
    return result


def source_summary(by_source: dict[str, dict]) -> dict:
    macro_f1_values = [metrics["macro_f1"] for metrics in by_source.values()]
    balanced_values = [metrics["balanced_accuracy"] for metrics in by_source.values()]
    worst_source = min(by_source, key=lambda source: (by_source[source]["macro_f1"], source))
    return {
        "source_count": len(by_source),
        "unweighted_mean_macro_f1_across_sources": round(
            statistics.mean(macro_f1_values), 6
        ),
        "worst_source_macro_f1": round(min(macro_f1_values), 6),
        "worst_source_dataset": worst_source,
        "unweighted_mean_balanced_accuracy_across_sources": round(
            statistics.mean(balanced_values), 6
        ),
    }


def candidate_score(candidate_report: dict, candidate_index: int) -> tuple:
    summary = candidate_report["validation_source_summary"]
    pooled = candidate_report["validation"]
    return (
        summary["unweighted_mean_macro_f1_across_sources"],
        summary["worst_source_macro_f1"],
        pooled["macro_f1"],
        pooled["balanced_accuracy"],
        -candidate_index,
    )


def selection_digest_payload(selected_hyperparameters: dict) -> dict:
    return {
        "selection_id": SELECTION_ID,
        "model_id": MODEL_ID,
        "input_split_sha256": EXPECTED_SPLIT_SHA256,
        "vectorizer": VECTORIZER_CONFIG,
        "classifier": {
            "type": "LogisticRegression",
            "solver": "liblinear",
            "max_iter": 2_000,
            "random_state": RANDOM_STATE,
            "threshold": THRESHOLD,
            **selected_hyperparameters,
        },
        "selection_policy": SELECTION_POLICY,
    }


def compute_selection_digest(selected_hyperparameters: dict) -> str:
    return canonical_digest(selection_digest_payload(selected_hyperparameters))


def validate_frozen_selection(selection: dict, selection_path: Path) -> None:
    if selection.get("selection_id") != SELECTION_ID:
        raise ValueError("Unexpected selection_id")
    if selection.get("status") != "FROZEN_VALIDATION_SELECTION_TEST_UNOPENED":
        raise ValueError("Selection is not frozen with test unopened")
    if selection.get("data", {}).get("input_split_sha256") != EXPECTED_SPLIT_SHA256:
        raise ValueError("Selection input split hash mismatch")
    scope = selection.get("data_access", {})
    if (
        scope.get("test_text_transformed") != 0
        or scope.get("test_labels_used") != 0
        or scope.get("excluded_rows_used") != 0
    ):
        raise ValueError("Selection artifact reports prohibited data access")
    selected = selection.get("selected_hyperparameters")
    if selected not in CANDIDATES:
        raise ValueError("Selected hyperparameters were not predeclared")
    expected_digest = compute_selection_digest(selected)
    if selection.get("selection_digest") != expected_digest:
        raise ValueError("Selection digest mismatch")


def source_label_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    return dict(
        sorted(
            Counter(
                f"{row['source_dataset']}|label={row['label']}" for row in rows
            ).items()
        )
    )
