"""Diagnose frozen Text Baseline V2 test errors without tuning the model.

This script is intentionally post-evaluation only. It reloads the exact frozen
model, verifies every pinned input, recomputes the stored test predictions, and
creates descriptive diagnostics plus a bounded manual-review queue. It never
fits a vectorizer or classifier and never changes source labels.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import joblib
import numpy as np

from mendeley_text_baseline_v2_common import (
    EXPECTED_PARTITION_COUNTS,
    EXPECTED_SPLIT_SHA256,
    MODEL_ID,
    THRESHOLD,
    evaluate_by_source,
    evaluate_classifier,
    read_final_data,
    sha256_file,
    source_summary,
    texts,
)


ANALYSIS_ID = "MENDELEY_TEXT_BASELINE_V2_ERROR_ANALYSIS"
STATUS = "FROZEN_DIAGNOSTIC_ERROR_ANALYSIS_NO_TUNING"
MODEL_SHA256 = "c58444996e0ae67a9739c588e3d088f1f57eb1af7f9105e10a647303ce72fc71"
RESULTS_SHA256 = "dfd0de31eccf380919908e347e98e4089f1d99fd12fb672f13f5d7cf7c52f91d"
PREDICTIONS_SHA256 = "21b3cae925a192df64c782e5d08591c5aacefa54f96b8f470aeadd89e8699cd1"
REPORT_NAME = "text_baseline_v2_error_analysis.json"
QUEUE_NAME = "text_baseline_v2_error_review_queue.jsonl"
QUEUE_PER_SOURCE_ERROR_TYPE = 8

EMAIL_RE = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b", re.IGNORECASE)
URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d .()\-]{7,}\d)(?!\w)")
LONG_ID_RE = re.compile(
    r"\b(?=[A-Za-z0-9]{26,64}\b)(?=[A-Za-z0-9]*[A-Za-z])(?=[A-Za-z0-9]*\d)[A-Za-z0-9]+\b"
)


def round_float(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def redact_excerpt(text: str, limit: int = 240) -> str:
    value = EMAIL_RE.sub("[EMAIL]", text)
    value = URL_RE.sub("[URL]", value)
    value = PHONE_RE.sub("[PHONE]", value)
    value = LONG_ID_RE.sub("[LONG_ID]", value)
    value = " ".join(value.split())
    return value[:limit].rstrip()


def confidence_band(confidence: float) -> str:
    if not 0.5 <= confidence <= 1.0:
        raise ValueError(f"Prediction confidence outside [0.5, 1.0]: {confidence}")
    if confidence >= 0.99:
        return "0.99-1.00"
    if confidence >= 0.90:
        return "0.90-0.99"
    if confidence >= 0.75:
        return "0.75-0.90"
    if confidence >= 0.60:
        return "0.60-0.75"
    return "0.50-0.60"


def similarity_band(value: float) -> str:
    if value <= 0.0:
        return "0.00"
    if value < 0.25:
        return "0.00-0.25"
    if value < 0.50:
        return "0.25-0.50"
    if value < 0.75:
        return "0.50-0.75"
    if value < 0.90:
        return "0.75-0.90"
    return "0.90-1.00"


def length_band(token_count: int) -> str:
    if token_count <= 12:
        return "0-12"
    if token_count <= 25:
        return "13-25"
    if token_count <= 50:
        return "26-50"
    if token_count <= 100:
        return "51-100"
    if token_count <= 200:
        return "101-200"
    return "201+"


def calibration_summary(
    truth: np.ndarray, probabilities: np.ndarray, *, bin_count: int = 10
) -> dict:
    if len(truth) != len(probabilities) or not len(truth):
        raise ValueError("Calibration arrays must be non-empty and aligned")
    if np.any((probabilities < 0.0) | (probabilities > 1.0)):
        raise ValueError("Probabilities must be within [0, 1]")
    bins = []
    weighted_gap = 0.0
    for index in range(bin_count):
        lower = index / bin_count
        upper = (index + 1) / bin_count
        if index == bin_count - 1:
            mask = (probabilities >= lower) & (probabilities <= upper)
        else:
            mask = (probabilities >= lower) & (probabilities < upper)
        count = int(mask.sum())
        if count:
            mean_score = float(np.mean(probabilities[mask]))
            positive_rate = float(np.mean(truth[mask]))
            gap = abs(mean_score - positive_rate)
            weighted_gap += count * gap
            mean_score_value = round_float(mean_score)
            positive_rate_value = round_float(positive_rate)
            gap_value = round_float(gap)
        else:
            mean_score_value = None
            positive_rate_value = None
            gap_value = None
        bins.append(
            {
                "lower_inclusive": round_float(lower, 1),
                "upper_inclusive_only_for_last_bin": round_float(upper, 1),
                "row_count": count,
                "mean_score_label_1": mean_score_value,
                "observed_positive_rate": positive_rate_value,
                "absolute_gap": gap_value,
            }
        )
    return {
        "binning": "10 fixed-width bins; left-closed/right-open except final bin includes 1.0",
        "brier_score": round_float(np.mean((probabilities - truth) ** 2)),
        "expected_calibration_error": round_float(weighted_gap / len(truth)),
        "bins": bins,
        "interpretation_warning": (
            "Calibration is against internal Mendeley source labels, not verified real-world scam outcomes."
        ),
    }


def numeric_summary(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "mean": None, "median": None, "q25": None, "q75": None}
    array = np.asarray(values, dtype=np.float64)
    return {
        "count": len(values),
        "mean": round_float(np.mean(array)),
        "median": round_float(np.median(array)),
        "q25": round_float(np.quantile(array, 0.25)),
        "q75": round_float(np.quantile(array, 0.75)),
    }


def top_row_contributions(
    feature_indices: np.ndarray,
    feature_values: np.ndarray,
    coefficients: np.ndarray,
    feature_names: np.ndarray,
    *,
    limit: int = 5,
) -> dict:
    if len(feature_indices) != len(feature_values):
        raise ValueError("Sparse row indices and values are not aligned")
    items = []
    for index, value in zip(feature_indices, feature_values):
        contribution = float(value) * float(coefficients[int(index)])
        if contribution == 0.0:
            continue
        items.append((str(feature_names[int(index)]), contribution))
    positive = sorted(
        (item for item in items if item[1] > 0.0),
        key=lambda item: (-item[1], item[0]),
    )[:limit]
    negative = sorted(
        (item for item in items if item[1] < 0.0),
        key=lambda item: (item[1], item[0]),
    )[:limit]
    return {
        "toward_label_1": [
            {"feature": feature, "logit_contribution": round_float(value, 8)}
            for feature, value in positive
        ],
        "toward_label_0": [
            {"feature": feature, "logit_contribution": round_float(value, 8)}
            for feature, value in negative
        ],
        "note": "Each value is TF-IDF feature value multiplied by the frozen logistic coefficient; intercept is separate.",
    }


def nearest_fit_neighbors(test_matrix, fit_matrix) -> tuple[np.ndarray, np.ndarray]:
    """Return max cosine similarity and deterministic nearest fit-row index.

    The frozen TF-IDF vectorizer applies L2 normalization, so sparse dot product
    equals cosine similarity. Ties are resolved by the lowest fit-row index.
    """

    similarities = (test_matrix @ fit_matrix.T).tocsr()
    maximum = np.zeros(test_matrix.shape[0], dtype=np.float64)
    nearest = np.full(test_matrix.shape[0], -1, dtype=np.int64)
    for row_index in range(test_matrix.shape[0]):
        start, end = similarities.indptr[row_index : row_index + 2]
        values = similarities.data[start:end]
        indices = similarities.indices[start:end]
        if len(values) == 0:
            continue
        max_value = float(np.max(values))
        tied = indices[values == max_value]
        maximum[row_index] = max_value
        nearest[row_index] = int(np.min(tied))
    return maximum, nearest


def vocabulary_coverage(analyzer, vocabulary: dict, text: str) -> tuple[int, int, float]:
    terms = set(analyzer(text))
    matched = sum(term in vocabulary for term in terms)
    coverage = matched / len(terms) if terms else 0.0
    return len(terms), matched, coverage


def load_predictions(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                raise ValueError(f"Blank prediction line: {line_number}")
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"Prediction line is not an object: {line_number}")
            rows.append(value)
    return rows


def compare_nested(actual: object, expected: object, label: str) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            raise ValueError(f"{label} key mismatch")
        for key in expected:
            compare_nested(actual[key], expected[key], f"{label}.{key}")
    elif isinstance(expected, float):
        if not math.isclose(float(actual), expected, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError(f"{label} mismatch: {actual} != {expected}")
    elif actual != expected:
        raise ValueError(f"{label} mismatch: {actual} != {expected}")


def summarize_subset(items: list[dict]) -> dict:
    return {
        "row_count": len(items),
        "surface_token_count": numeric_summary(
            [float(item["surface_token_count"]) for item in items]
        ),
        "unique_vectorizer_term_coverage": numeric_summary(
            [float(item["unique_vectorizer_term_coverage"]) for item in items]
        ),
        "nearest_fit_cosine_similarity": numeric_summary(
            [float(item["nearest_fit_cosine_similarity"]) for item in items]
        ),
        "prediction_confidence": numeric_summary(
            [float(item["prediction_confidence"]) for item in items]
        ),
    }


def select_review_queue(
    errors: list[dict], *, per_source_error_type: int = QUEUE_PER_SOURCE_ERROR_TYPE
) -> tuple[list[dict], dict]:
    if per_source_error_type <= 0:
        raise ValueError("Queue cap must be positive")
    queue = []
    seen_groups = set()
    strata = {}
    sources = sorted({item["source_dataset"] for item in errors})
    for source in sources:
        for error_type in ("false_positive", "false_negative"):
            candidates = sorted(
                (
                    item
                    for item in errors
                    if item["source_dataset"] == source
                    and item["error_type"] == error_type
                ),
                key=lambda item: (-item["prediction_confidence"], item["record_id"]),
            )
            selected = []
            for item in candidates:
                if item["split_group_id"] in seen_groups:
                    continue
                seen_groups.add(item["split_group_id"])
                selected.append(item)
                if len(selected) == per_source_error_type:
                    break
            stratum = f"{source}|{error_type}"
            strata[stratum] = {
                "available_error_rows": len(candidates),
                "selected_unique_groups": len(selected),
                "cap": per_source_error_type,
            }
            queue.extend(selected)
    queue_records = []
    for rank, item in enumerate(queue, start=1):
        queue_records.append(
            {
                "queue_rank": rank,
                "review_purpose": "diagnose frozen internal-test error; do not relabel or tune from this queue",
                "record_id": item["record_id"],
                "split_group_id": item["split_group_id"],
                "source_dataset": item["source_dataset"],
                "source_label": item["source_label"],
                "predicted_label": item["predicted_label"],
                "error_type": item["error_type"],
                "score_label_1": item["score_label_1"],
                "prediction_confidence": item["prediction_confidence"],
                "confidence_band": item["confidence_band"],
                "surface_token_count": item["surface_token_count"],
                "length_band": item["length_band"],
                "unique_analyzed_term_count": item["unique_analyzed_term_count"],
                "matched_vocabulary_term_count": item["matched_vocabulary_term_count"],
                "unique_vectorizer_term_coverage": item[
                    "unique_vectorizer_term_coverage"
                ],
                "nearest_fit_record_id": item["nearest_fit_record_id"],
                "nearest_fit_source_dataset": item[
                    "nearest_fit_source_dataset"
                ],
                "nearest_fit_partition": item["nearest_fit_partition"],
                "nearest_fit_cosine_similarity": item[
                    "nearest_fit_cosine_similarity"
                ],
                "feature_contributions": item["feature_contributions"],
                "redacted_text_excerpt": item["redacted_text_excerpt"],
            }
        )
    return queue_records, strata


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def prepare_output_paths(output_dir: Path, *, overwrite: bool) -> dict[str, Path]:
    paths = {"report": output_dir / REPORT_NAME, "review_queue": output_dir / QUEUE_NAME}
    existing = [path for path in paths.values() if path.exists()]
    if existing and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing artifact: {existing[0]}")
    output_dir.mkdir(parents=True, exist_ok=True)
    return paths


def analyze_frozen_errors(
    input_path: Path,
    model_path: Path,
    predictions_path: Path,
    results_path: Path,
    output_dir: Path,
    *,
    run_at: str,
    overwrite: bool = False,
) -> dict:
    expected_hashes = {
        "group_split_dataset": EXPECTED_SPLIT_SHA256,
        "model": MODEL_SHA256,
        "results": RESULTS_SHA256,
        "test_predictions": PREDICTIONS_SHA256,
    }
    input_paths = {
        "group_split_dataset": input_path,
        "model": model_path,
        "results": results_path,
        "test_predictions": predictions_path,
    }
    observed_hashes = {role: sha256_file(path) for role, path in input_paths.items()}
    if observed_hashes != expected_hashes:
        raise ValueError(
            "Frozen input SHA-256 mismatch: "
            + ", ".join(
                role for role in expected_hashes if observed_hashes[role] != expected_hashes[role]
            )
        )

    splits, access = read_final_data(input_path)
    fit_rows = splits["train"] + splits["validation"]
    test_rows = splits["test"]
    if len(fit_rows) != 4_754 or len(test_rows) != 838:
        raise ValueError("Unexpected frozen fit/test row counts")

    bundle = joblib.load(model_path)
    if bundle.get("model_id") != MODEL_ID:
        raise ValueError("Unexpected model bundle ID")
    metadata = bundle.get("metadata", {})
    if metadata.get("fit_partitions") != ["train", "validation"]:
        raise ValueError("Frozen model fit partition contract mismatch")
    if metadata.get("excluded_partitions") != ["auxiliary", "quarantine"]:
        raise ValueError("Frozen model excluded partition contract mismatch")
    if metadata.get("threshold") != THRESHOLD:
        raise ValueError("Frozen model threshold mismatch")
    vectorizer = bundle["vectorizer"]
    classifier = bundle["classifier"]
    if getattr(vectorizer, "norm", None) != "l2":
        raise ValueError("Nearest-neighbor diagnostic requires frozen L2 TF-IDF")

    fit_matrix = vectorizer.transform(texts(fit_rows)).tocsr()
    test_matrix = vectorizer.transform(texts(test_rows)).tocsr()
    test_metrics, recomputed_predictions, recomputed_probabilities = evaluate_classifier(
        classifier, test_matrix, test_rows
    )
    test_by_source = evaluate_by_source(
        test_rows, recomputed_predictions, recomputed_probabilities
    )
    results = json.loads(results_path.read_text(encoding="utf-8"))
    compare_nested(test_metrics, results["test"], "results.test")
    compare_nested(
        test_by_source, results["test_by_source_dataset"], "results.test_by_source_dataset"
    )
    compare_nested(
        source_summary(test_by_source), results["test_source_summary"], "results.test_source_summary"
    )

    stored_predictions = load_predictions(predictions_path)
    if len(stored_predictions) != len(test_rows):
        raise ValueError("Stored prediction row count mismatch")
    stored_ids = [row.get("record_id") for row in stored_predictions]
    expected_ids = [row["record_id"] for row in test_rows]
    if stored_ids != expected_ids or len(set(stored_ids)) != len(stored_ids):
        raise ValueError("Stored predictions do not cover ordered test records exactly once")
    for index, (stored, row) in enumerate(zip(stored_predictions, test_rows)):
        if stored.get("partition") != "test":
            raise ValueError(f"Non-test stored prediction at row {index}")
        if stored.get("split_group_id") != row["split_group_id"]:
            raise ValueError(f"Stored split_group_id mismatch: {row['record_id']}")
        if stored.get("source_dataset") != row["source_dataset"]:
            raise ValueError(f"Stored source mismatch: {row['record_id']}")
        if int(stored.get("source_label")) != int(row["label"]):
            raise ValueError(f"Stored source label mismatch: {row['record_id']}")
        if int(stored.get("predicted_label")) != int(recomputed_predictions[index]):
            raise ValueError(f"Stored prediction mismatch: {row['record_id']}")
        if bool(stored.get("correct")) != bool(
            int(recomputed_predictions[index]) == int(row["label"])
        ):
            raise ValueError(f"Stored correctness mismatch: {row['record_id']}")
        if not math.isclose(
            float(stored.get("score_label_1")),
            float(recomputed_probabilities[index]),
            rel_tol=0.0,
            abs_tol=5.1e-11,
        ):
            raise ValueError(f"Stored probability mismatch: {row['record_id']}")

    nearest_similarity, nearest_indices = nearest_fit_neighbors(test_matrix, fit_matrix)
    analyzer = vectorizer.build_analyzer()
    vocabulary = vectorizer.vocabulary_
    feature_names = vectorizer.get_feature_names_out()
    coefficients = classifier.coef_[0]
    diagnostics = []
    errors = []
    for index, row in enumerate(test_rows):
        source_label = int(row["label"])
        predicted_label = int(recomputed_predictions[index])
        score = float(recomputed_probabilities[index])
        confidence = score if predicted_label == 1 else 1.0 - score
        nearest_index = int(nearest_indices[index])
        nearest_row = fit_rows[nearest_index] if nearest_index >= 0 else None
        term_count, matched_count, coverage = vocabulary_coverage(
            analyzer, vocabulary, row.get("text_content") or ""
        )
        surface_tokens = len((row.get("text_content") or "").split())
        item = {
            "record_id": row["record_id"],
            "split_group_id": row["split_group_id"],
            "source_dataset": row["source_dataset"],
            "source_label": source_label,
            "predicted_label": predicted_label,
            "correct": predicted_label == source_label,
            "score_label_1": round_float(score, 10),
            "prediction_confidence": round_float(confidence, 10),
            "confidence_band": confidence_band(confidence),
            "surface_token_count": surface_tokens,
            "length_band": length_band(surface_tokens),
            "unique_analyzed_term_count": term_count,
            "matched_vocabulary_term_count": matched_count,
            "unique_vectorizer_term_coverage": round_float(coverage),
            "nearest_fit_record_id": nearest_row["record_id"] if nearest_row else None,
            "nearest_fit_source_dataset": nearest_row["source_dataset"] if nearest_row else None,
            "nearest_fit_partition": nearest_row["partition"] if nearest_row else None,
            "nearest_fit_cosine_similarity": round_float(nearest_similarity[index]),
        }
        diagnostics.append(item)
        if item["correct"]:
            continue
        item["error_type"] = "false_positive" if predicted_label == 1 else "false_negative"
        sparse_row = test_matrix.getrow(index)
        item["feature_contributions"] = top_row_contributions(
            sparse_row.indices,
            sparse_row.data,
            coefficients,
            feature_names,
        )
        item["redacted_text_excerpt"] = redact_excerpt(row.get("text_content") or "")
        errors.append(item)

    paths = prepare_output_paths(output_dir, overwrite=overwrite)
    queue, queue_strata = select_review_queue(errors)
    write_jsonl(paths["review_queue"], queue)
    queue_sha256 = sha256_file(paths["review_queue"])

    by_source = {}
    for source in sorted({item["source_dataset"] for item in diagnostics}):
        source_items = [item for item in diagnostics if item["source_dataset"] == source]
        source_errors = [item for item in source_items if not item["correct"]]
        by_source[source] = {
            "row_count": len(source_items),
            "error_count": len(source_errors),
            "error_rate": round_float(len(source_errors) / len(source_items)),
            "false_positive_count": sum(
                item["error_type"] == "false_positive" for item in source_errors
            ),
            "false_negative_count": sum(
                item["error_type"] == "false_negative" for item in source_errors
            ),
            "high_confidence_error_count_gte_0_90": sum(
                item["prediction_confidence"] >= 0.90 for item in source_errors
            ),
            "macro_f1": test_by_source[source]["macro_f1"],
            "roc_auc": test_by_source[source]["roc_auc"],
        }

    by_actual_label = {}
    for label in (0, 1):
        label_items = [item for item in diagnostics if item["source_label"] == label]
        label_errors = [item for item in label_items if not item["correct"]]
        by_actual_label[str(label)] = {
            "row_count": len(label_items),
            "error_count": len(label_errors),
            "error_rate": round_float(len(label_errors) / len(label_items)),
        }

    group_counts = Counter(item["split_group_id"] for item in errors)
    error_groups = [
        {
            "split_group_id": group,
            "error_count": count,
            "source_datasets": sorted(
                {item["source_dataset"] for item in errors if item["split_group_id"] == group}
            ),
            "record_ids": sorted(
                item["record_id"] for item in errors if item["split_group_id"] == group
            )[:10],
        }
        for group, count in sorted(group_counts.items(), key=lambda item: (-item[1], item[0]))
    ]

    confidence_counts = Counter(item["confidence_band"] for item in errors)
    similarity_counts = Counter(
        similarity_band(item["nearest_fit_cosine_similarity"]) for item in errors
    )
    length_counts = Counter(item["length_band"] for item in errors)
    truth = np.asarray([int(row["label"]) for row in test_rows], dtype=np.float64)
    error_count = len(errors)
    twitter_errors = by_source["twitter_bot_detection"]["error_count"]
    model_hash_after = sha256_file(model_path)
    quality_gates = {
        "all_frozen_input_hashes_match": observed_hashes == expected_hashes,
        "model_hash_unchanged_during_analysis": model_hash_after == MODEL_SHA256,
        "split_partition_counts_match": access["partition_counts_scanned"]
        == EXPECTED_PARTITION_COUNTS,
        "fit_reference_is_train_plus_validation_only": len(fit_rows) == 4_754
        and {row["partition"] for row in fit_rows} == {"train", "validation"},
        "test_rows_analyzed_exact": len(test_rows) == 838,
        "stored_predictions_cover_test_once": len(stored_ids) == len(set(stored_ids)) == 838,
        "stored_predictions_reproduced": True,
        "published_test_metrics_reproduced": True,
        "auxiliary_rows_used_zero": access["auxiliary_rows_loaded_for_modeling"] == 0,
        "quarantine_rows_used_zero": access["quarantine_rows_loaded_for_modeling"] == 0,
        "model_or_vectorizer_fit_calls_zero": True,
        "queue_contains_errors_only": all(row["source_label"] != row["predicted_label"] for row in queue),
        "queue_split_groups_unique": len(queue)
        == len({row["split_group_id"] for row in queue}),
        "queue_creates_no_labels": all("new_label" not in row for row in queue),
    }
    failed = sorted(name for name, passed in quality_gates.items() if not passed)
    if failed:
        raise ValueError("Error-analysis quality gates failed: " + ", ".join(failed))

    report = {
        "analysis_id": ANALYSIS_ID,
        "run_at": run_at,
        "status": STATUS,
        "model_id": MODEL_ID,
        "purpose": "Describe frozen internal-test failure modes without selecting or changing any model component.",
        "label_semantics": results["label_semantics"],
        "inputs": {
            role: {
                "file_name": path.name,
                "sha256": observed_hashes[role],
            }
            for role, path in input_paths.items()
        },
        "method": {
            "test_partition_role": "diagnostic-only after final evaluation",
            "model_fit_or_refit": False,
            "threshold_changed": False,
            "feature_policy_changed": False,
            "candidate_selection_performed": False,
            "fit_reference_for_similarity": ["train", "validation"],
            "nearest_similarity": "maximum sparse cosine similarity in the frozen L2 word TF-IDF space",
            "vocabulary_coverage": "share of unique analyzer-produced unigrams/bigrams present in the frozen vocabulary",
            "feature_contribution": "row TF-IDF value multiplied by frozen logistic coefficient",
            "review_queue_policy": (
                f"up to {QUEUE_PER_SOURCE_ERROR_TYPE} highest-confidence unique split groups "
                "per source_dataset and error_type"
            ),
        },
        "counts": {
            "final_fit_reference_rows": len(fit_rows),
            "test_rows": len(test_rows),
            "correct_rows": len(test_rows) - error_count,
            "error_rows": error_count,
            "error_rate": round_float(error_count / len(test_rows)),
            "false_positive_count": sum(
                item["error_type"] == "false_positive" for item in errors
            ),
            "false_negative_count": sum(
                item["error_type"] == "false_negative" for item in errors
            ),
            "high_confidence_error_count_gte_0_90": sum(
                item["prediction_confidence"] >= 0.90 for item in errors
            ),
            "unique_error_split_groups": len(group_counts),
            "review_queue_rows": len(queue),
            "review_queue_unique_split_groups": len(
                {row["split_group_id"] for row in queue}
            ),
        },
        "error_concentration": {
            "twitter_bot_detection_error_count": twitter_errors,
            "twitter_bot_detection_share_of_all_errors": round_float(
                twitter_errors / error_count
            ),
        },
        "by_source_dataset": by_source,
        "by_actual_label": by_actual_label,
        "calibration": calibration_summary(truth, recomputed_probabilities),
        "correct_vs_error_diagnostics": {
            "correct": summarize_subset([item for item in diagnostics if item["correct"]]),
            "error": summarize_subset(errors),
        },
        "error_confidence_band_counts": dict(sorted(confidence_counts.items())),
        "error_length_band_counts": dict(sorted(length_counts.items())),
        "error_nearest_fit_similarity_band_counts": dict(sorted(similarity_counts.items())),
        "largest_error_groups": error_groups[:20],
        "review_queue_strata": queue_strata,
        "artifacts": {
            "review_queue": {
                "file_name": paths["review_queue"].name,
                "sha256": queue_sha256,
                "row_count": len(queue),
            }
        },
        "quality_gates": quality_gates,
        "safety_contract": {
            "raw_files_modified": False,
            "split_file_modified": False,
            "model_file_modified": False,
            "source_labels_changed": 0,
            "labels_created": 0,
            "network_operations": 0,
            "training_allowed": False,
            "domain_access_allowed": False,
            "test_used_for_tuning": False,
            "deployment_allowed": False,
        },
        "interpretation_limits": [
            "The source label is a harmonized Mendeley benchmark label, not verified investment-scam ground truth.",
            "This analysis may explain errors but must not be used to tune the frozen V2 model or threshold and then re-report the same test.",
            "Nearest-fit similarity and feature contributions are descriptive model-space diagnostics, not causal evidence.",
            "The review queue is not a relabeling queue and creates no thesis, Gold, or adjudicated labels.",
        ],
        "next_gate": "Evaluate the unchanged frozen model on evidence-backed curated or genuinely external cases.",
    }
    paths["report"].write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-at", required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    report = analyze_frozen_errors(
        args.input,
        args.model,
        args.predictions,
        args.results,
        args.output_dir,
        run_at=args.run_at,
        overwrite=args.overwrite,
    )
    print(
        json.dumps(
            {
                "analysis_id": report["analysis_id"],
                "status": report["status"],
                "counts": report["counts"],
                "error_concentration": report["error_concentration"],
                "calibration": {
                    "brier_score": report["calibration"]["brier_score"],
                    "expected_calibration_error": report["calibration"][
                        "expected_calibration_error"
                    ],
                },
                "output_dir": str(args.output_dir),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
