"""Evaluate source-balanced training for the frozen Mendeley text baseline.

source_dataset is used only to calculate training sample weights and to report
stratified metrics. It is never included in the TF-IDF feature matrix.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from analyze_mendeley_metadata_ablation import (
    LABEL_SEMANTICS,
    evaluate_by_source,
    evaluate_classifier,
    expanded_metrics,
    labels,
    make_classifier,
    make_vectorizer,
    paired_comparison,
    read_rows,
    sha256_file,
    texts,
)


ANALYSIS_ID = "MENDELEY_SOURCE_BALANCE_ABLATION_V1"
FIXED_C = 2.0
STRATEGIES = (
    "unweighted",
    "sqrt_inverse_source_frequency",
    "inverse_source_frequency",
    "sqrt_inverse_source_label_frequency",
    "inverse_source_label_frequency",
)


def compute_sample_weights(rows, strategy: str) -> np.ndarray:
    if strategy not in STRATEGIES:
        raise ValueError(f"Unknown weighting strategy: {strategy}")
    if not rows:
        raise ValueError("Cannot weight an empty training set")

    source_counts = Counter(row["source_dataset"] for row in rows)
    source_label_counts = Counter((row["source_dataset"], row["label"]) for row in rows)
    raw = []
    for row in rows:
        source_count = source_counts[row["source_dataset"]]
        cell_count = source_label_counts[(row["source_dataset"], row["label"])]
        if strategy == "unweighted":
            weight = 1.0
        elif strategy == "sqrt_inverse_source_frequency":
            weight = 1.0 / math.sqrt(source_count)
        elif strategy == "inverse_source_frequency":
            weight = 1.0 / source_count
        elif strategy == "sqrt_inverse_source_label_frequency":
            weight = 1.0 / math.sqrt(cell_count)
        else:
            weight = 1.0 / cell_count
        raw.append(weight)

    weights = np.asarray(raw, dtype=np.float64)
    weights /= float(np.mean(weights))
    if not np.all(np.isfinite(weights)) or np.any(weights <= 0):
        raise ValueError(f"Invalid sample weights for {strategy}")
    return weights


def weight_profile(rows, weights) -> dict:
    total = float(np.sum(weights))
    effective_n = total * total / float(np.sum(np.square(weights)))
    source_totals = Counter()
    source_label_totals = Counter()
    for row, weight in zip(rows, weights):
        source_totals[row["source_dataset"]] += float(weight)
        source_label_totals[(row["source_dataset"], row["label"])] += float(weight)
    return {
        "row_count": len(rows),
        "mean_weight": round(float(np.mean(weights)), 12),
        "minimum_weight": round(float(np.min(weights)), 12),
        "maximum_weight": round(float(np.max(weights)), 12),
        "effective_sample_size": round(effective_n, 3),
        "effective_sample_ratio": round(effective_n / len(rows), 6),
        "total_weight_by_source_dataset": {
            source: round(value, 6) for source, value in sorted(source_totals.items())
        },
        "total_weight_by_source_and_label": {
            f"{source}|{label}": round(value, 6)
            for (source, label), value in sorted(source_label_totals.items())
        },
    }


def source_summary(metrics_by_source: dict) -> dict:
    macro_values = [metrics["macro_f1"] for metrics in metrics_by_source.values()]
    balanced_values = [metrics["balanced_accuracy"] for metrics in metrics_by_source.values()]
    return {
        "unweighted_mean_macro_f1_across_sources": round(statistics.mean(macro_values), 6),
        "worst_source_macro_f1": round(min(macro_values), 6),
        "best_source_macro_f1": round(max(macro_values), 6),
        "unweighted_mean_balanced_accuracy_across_sources": round(
            statistics.mean(balanced_values), 6
        ),
        "worst_source_balanced_accuracy": round(min(balanced_values), 6),
    }


def selection_score(strategy: str, report: dict) -> tuple:
    summary = report["validation_source_summary"]
    return (
        summary["unweighted_mean_macro_f1_across_sources"],
        summary["worst_source_macro_f1"],
        report["validation"]["macro_f1"],
        report["validation"]["f1_label_1"],
        -STRATEGIES.index(strategy),
    )


def mean_across_held_out_sources(results: dict) -> dict:
    metrics = (
        "accuracy",
        "f1_label_1",
        "macro_f1",
        "balanced_accuracy",
        "roc_auc",
        "average_precision",
    )
    return {
        metric: round(statistics.mean(item["metrics"][metric] for item in results.values()), 6)
        for metric in metrics
    }


def leave_one_source_out(splits) -> dict:
    sources = sorted({row["source_dataset"] for rows in splits.values() for row in rows})
    results = {strategy: {} for strategy in STRATEGIES}
    for held_out in sources:
        train_rows = [row for row in splits["train"] if row["source_dataset"] != held_out]
        test_rows = [row for row in splits["test"] if row["source_dataset"] == held_out]
        vectorizer = make_vectorizer()
        train_matrix = vectorizer.fit_transform(texts(train_rows))
        test_matrix = vectorizer.transform(texts(test_rows))
        train_truth = labels(train_rows)
        for strategy in STRATEGIES:
            weights = compute_sample_weights(train_rows, strategy)
            classifier = make_classifier(FIXED_C, None)
            classifier.fit(train_matrix, train_truth, sample_weight=weights)
            metrics, _, _ = evaluate_classifier(classifier, test_matrix, test_rows)
            results[strategy][held_out] = {
                "train_rows_from_other_sources": len(train_rows),
                "held_out_test_rows": len(test_rows),
                "metrics": metrics,
            }
    return results


def write_predictions(path, rows, predictions, probabilities):
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for index, row in enumerate(rows):
            record = {
                "record_id": row["record_id"],
                "partition": "test",
                "source_dataset": row["source_dataset"],
                "source_label": int(row["label"]),
                "predictions": {
                    strategy: {
                        "predicted_label": int(predictions[strategy][index]),
                        "score_label_1": round(float(probabilities[strategy][index]), 10),
                    }
                    for strategy in STRATEGIES
                },
            }
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--run-at",
        help="Optional fixed ISO-8601 timestamp for bit-for-bit reproduction of a frozen run.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Explicitly allow replacement of existing output artifacts.",
    )
    args = parser.parse_args()

    results_path = args.output_dir / "source_balance_ablation_results_v1.json"
    predictions_path = args.output_dir / "source_balance_ablation_test_predictions_v1.jsonl"
    existing = [path for path in (results_path, predictions_path) if path.exists()]
    if existing and not args.overwrite:
        raise FileExistsError(
            "Refusing to overwrite frozen-style artifacts without --overwrite: "
            + ", ".join(str(path) for path in existing)
        )
    if args.run_at:
        parsed_run_at = datetime.fromisoformat(args.run_at.replace("Z", "+00:00"))
        if parsed_run_at.tzinfo is None:
            raise ValueError("--run-at must include a timezone offset")
        run_at = parsed_run_at.isoformat()
    else:
        run_at = datetime.now(timezone.utc).isoformat()

    splits = read_rows(args.input)
    train_rows = splits["train"]
    validation_rows = splits["validation"]
    vectorizer = make_vectorizer()
    train_matrix = vectorizer.fit_transform(texts(train_rows))
    validation_matrix = vectorizer.transform(texts(validation_rows))
    train_truth = labels(train_rows)

    # Phase 1: every strategy and the fixed model configuration are evaluated on validation.
    classifiers = {}
    strategies_report = {}
    for strategy in STRATEGIES:
        weights = compute_sample_weights(train_rows, strategy)
        classifier = make_classifier(FIXED_C, None)
        classifier.fit(train_matrix, train_truth, sample_weight=weights)
        validation_metrics, validation_predictions, validation_probabilities = evaluate_classifier(
            classifier, validation_matrix, validation_rows
        )
        validation_by_source = evaluate_by_source(
            validation_predictions, validation_probabilities, validation_rows
        )
        classifiers[strategy] = classifier
        strategies_report[strategy] = {
            "weight_profile": weight_profile(train_rows, weights),
            "validation": validation_metrics,
            "validation_by_source_dataset": validation_by_source,
            "validation_source_summary": source_summary(validation_by_source),
        }

    selected_strategy = max(
        STRATEGIES, key=lambda strategy: selection_score(strategy, strategies_report[strategy])
    )

    # Phase 2: the strategy is frozen. Test is transformed and evaluated once.
    test_rows = splits["test"]
    test_matrix = vectorizer.transform(texts(test_rows))
    test_truth = labels(test_rows)
    test_predictions = {}
    test_probabilities = {}
    for strategy in STRATEGIES:
        test_metrics, predictions, probabilities = evaluate_classifier(
            classifiers[strategy], test_matrix, test_rows
        )
        test_by_source = evaluate_by_source(predictions, probabilities, test_rows)
        strategies_report[strategy]["test"] = test_metrics
        strategies_report[strategy]["test_by_source_dataset"] = test_by_source
        strategies_report[strategy]["test_source_summary"] = source_summary(test_by_source)
        test_predictions[strategy] = predictions
        test_probabilities[strategy] = probabilities

    cross_source = leave_one_source_out(splits)
    for strategy in STRATEGIES:
        strategies_report[strategy]["leave_one_source_out"] = cross_source[strategy]
        strategies_report[strategy]["leave_one_source_out_mean_across_sources"] = (
            mean_across_held_out_sources(cross_source[strategy])
        )
        strategies_report[strategy]["leave_one_source_out_worst_source_macro_f1"] = round(
            min(item["metrics"]["macro_f1"] for item in cross_source[strategy].values()), 6
        )

    paired = {
        strategy: paired_comparison(
            test_predictions["unweighted"], test_predictions[strategy], test_truth
        )
        for strategy in STRATEGIES
        if strategy != "unweighted"
    }

    baseline = strategies_report["unweighted"]
    selected = strategies_report[selected_strategy]
    selected_paired = paired.get(selected_strategy)
    promotion_checks = {
        "validation_selected_a_weighted_strategy": selected_strategy != "unweighted",
        "internal_test_macro_f1_improves": selected["test"]["macro_f1"]
        > baseline["test"]["macro_f1"],
        "leave_one_source_out_mean_macro_f1_improves": selected[
            "leave_one_source_out_mean_across_sources"
        ]["macro_f1"]
        > baseline["leave_one_source_out_mean_across_sources"]["macro_f1"],
        "leave_one_source_out_worst_source_macro_f1_not_worse": selected[
            "leave_one_source_out_worst_source_macro_f1"
        ]
        >= baseline["leave_one_source_out_worst_source_macro_f1"],
        "paired_test_mcnemar_significant_at_0_05": bool(
            selected_paired and selected_paired["statistically_significant_at_0_05"]
        ),
    }
    promote = all(promotion_checks.values())

    source_counts = Counter(row["source_dataset"] for row in train_rows)
    source_label_counts = Counter((row["source_dataset"], row["label"]) for row in train_rows)
    report = {
        "analysis_id": ANALYSIS_ID,
        "run_at": run_at,
        "status": "FROZEN_RESEARCH_ABLATION_NOT_FOR_DEPLOYMENT",
        "label_semantics": LABEL_SEMANTICS,
        "data": {
            "input": str(args.input),
            "input_sha256": sha256_file(args.input),
            "partition_counts": {name: len(rows) for name, rows in splits.items()},
            "split_group_cross_partition_count": 0,
            "train_source_counts": dict(sorted(source_counts.items())),
            "train_source_label_counts": {
                f"{source}|{label}": count
                for (source, label), count in sorted(source_label_counts.items())
            },
        },
        "model_contract": {
            "feature": "text_content TF-IDF only",
            "source_dataset_in_feature_matrix": False,
            "source_dataset_allowed_uses": [
                "training sample-weight calculation",
                "validation-only strategy selection",
                "stratified reporting",
                "leave-one-source-out evaluation",
            ],
            "classifier": "LogisticRegression",
            "fixed_hyperparameters": {
                "C": FIXED_C,
                "class_weight": None,
                "solver": "liblinear",
                "threshold": 0.5,
            },
            "vectorizer": {
                "type": "tfidf",
                "ngram_range": [1, 2],
                "min_df": 2,
                "max_df": 0.995,
                "max_features": 100000,
                "sublinear_tf": True,
                "full_train_vocabulary_size": len(vectorizer.vocabulary_),
            },
        },
        "selection_policy": {
            "candidate_strategies": list(STRATEGIES),
            "selection_partitions": ["train", "validation"],
            "test_used_for_vectorizer_or_model_fitting": False,
            "test_used_for_strategy_selection": False,
            "primary_metric": "unweighted mean of per-source validation Macro-F1",
            "tie_breakers": [
                "worst-source validation Macro-F1",
                "pooled validation Macro-F1",
                "pooled validation F1 label 1",
                "simpler earlier strategy",
            ],
            "selected_strategy_on_validation": selected_strategy,
        },
        "weighting_definitions": {
            "unweighted": "all train rows receive equal weight",
            "sqrt_inverse_source_frequency": "row weight is proportional to 1/sqrt(train rows in its source)",
            "inverse_source_frequency": "row weight is proportional to 1/(train rows in its source)",
            "sqrt_inverse_source_label_frequency": "row weight is proportional to 1/sqrt(train rows in its source-label cell)",
            "inverse_source_label_frequency": "row weight is proportional to 1/(train rows in its source-label cell)",
            "normalization": "each strategy is normalized to mean train weight 1",
        },
        "strategies": strategies_report,
        "paired_test_comparisons_against_unweighted": paired,
        "decision": {
            "selected_strategy_on_validation": selected_strategy,
            "promotion_checks": promotion_checks,
            "promote_to_primary_internal_baseline": promote,
            "deployment_allowed": False,
            "policy": (
                "A validation-selected weighted strategy can replace the internal baseline only if it "
                "improves internal-test Macro-F1, improves mean leave-one-source-out Macro-F1, does not "
                "reduce the worst held-out-source Macro-F1, and has a significant paired McNemar test."
            ),
        },
        "prohibited_claims": [
            "Do not describe source label 1 as regulator-verified investment fraud.",
            "Do not describe scores as real-world scam probabilities.",
            "Do not include source_dataset in deployed or experimental predictive features.",
            "Do not deploy this ablation for blocking, enforcement or financial decisions.",
        ],
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    results_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_predictions(predictions_path, test_rows, test_predictions, test_probabilities)
    print(json.dumps({
        "analysis_id": ANALYSIS_ID,
        "input_sha256": report["data"]["input_sha256"],
        "selected_strategy_on_validation": selected_strategy,
        "decision": report["decision"],
        "unweighted": {
            "validation": baseline["validation"],
            "test": baseline["test"],
            "leave_one_source_out_mean": baseline["leave_one_source_out_mean_across_sources"],
            "leave_one_source_out_worst_source_macro_f1": baseline[
                "leave_one_source_out_worst_source_macro_f1"
            ],
        },
        "selected": {
            "validation": selected["validation"],
            "validation_source_summary": selected["validation_source_summary"],
            "test": selected["test"],
            "test_source_summary": selected["test_source_summary"],
            "leave_one_source_out_mean": selected["leave_one_source_out_mean_across_sources"],
            "leave_one_source_out_worst_source_macro_f1": selected[
                "leave_one_source_out_worst_source_macro_f1"
            ],
            "paired_vs_unweighted": selected_paired,
        },
        "outputs": {"results": str(results_path), "predictions": str(predictions_path)},
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
