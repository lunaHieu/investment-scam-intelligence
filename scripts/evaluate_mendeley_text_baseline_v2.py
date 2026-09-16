"""Fit and evaluate the frozen Mendeley text baseline V2 on internal test.

This phase refuses to run unless the separate validation-only selection artifact
is frozen and internally consistent. It then loads benchmark rows, refits the
selected word TF-IDF + Logistic Regression model on train+validation, and opens
test once for reporting. Auxiliary and quarantine rows remain excluded.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np

from mendeley_text_baseline_v2_common import (
    BENCHMARK_PARTITIONS,
    EXPECTED_PARTITION_COUNTS,
    EXPECTED_SPLIT_SHA256,
    LABEL_SEMANTICS,
    MODEL_ID,
    RANDOM_STATE,
    SELECTION_ID,
    THRESHOLD,
    VECTORIZER_CONFIG,
    evaluate_by_source,
    evaluate_classifier,
    fit_classifier,
    labels,
    make_classifier,
    make_vectorizer,
    read_final_data,
    sha256_file,
    source_label_counts,
    source_summary,
    texts,
    validate_frozen_selection,
)


RESULTS_NAME = "text_baseline_v2_results.json"
MODEL_NAME = "text_baseline_v2_model.joblib"
PREDICTIONS_NAME = "text_baseline_v2_test_predictions.jsonl"


def safe_feature(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )


def top_coefficients(vectorizer, classifier, count: int = 30) -> dict:
    features = vectorizer.get_feature_names_out()
    coefficients = classifier.coef_[0]
    if len(features) != len(coefficients):
        raise ValueError("Feature/coefficient length mismatch")
    positive = np.argsort(coefficients)[-count:][::-1]
    negative = np.argsort(coefficients)[:count]
    return {
        "toward_label_1": [
            {
                "feature": safe_feature(str(features[index])),
                "coefficient": round(float(coefficients[index]), 8),
            }
            for index in positive
        ],
        "toward_label_0": [
            {
                "feature": safe_feature(str(features[index])),
                "coefficient": round(float(coefficients[index]), 8),
            }
            for index in negative
        ],
        "interpretation_warning": (
            "Coefficients are benchmark associations, may encode source/style artifacts, "
            "and are not causal evidence of investment fraud."
        ),
    }


def write_predictions(
    path: Path,
    rows: list[dict[str, str]],
    predictions: np.ndarray,
    probabilities: np.ndarray,
) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row, prediction, probability in zip(rows, predictions, probabilities):
            record = {
                "record_id": row["record_id"],
                "partition": "test",
                "split_group_id": row["split_group_id"],
                "source_dataset": row["source_dataset"],
                "source_label": int(row["label"]),
                "predicted_label": int(prediction),
                "score_label_1": round(float(probability), 10),
                "correct": bool(int(prediction) == int(row["label"])),
                "score_semantics": "internal Mendeley source-label score; not real-world scam probability",
            }
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def prepare_output_paths(output_dir: Path, *, overwrite: bool) -> dict[str, Path]:
    paths = {
        "model": output_dir / MODEL_NAME,
        "results": output_dir / RESULTS_NAME,
        "test_predictions": output_dir / PREDICTIONS_NAME,
    }
    existing = [path for path in paths.values() if path.exists()]
    if existing and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing artifact: {existing[0]}")
    output_dir.mkdir(parents=True, exist_ok=True)
    return paths


def evaluate_frozen_selection(
    input_path: Path,
    selection_path: Path,
    output_dir: Path,
    *,
    run_at: str,
    overwrite: bool = False,
) -> dict:
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    validate_frozen_selection(selection, selection_path)
    selection_sha256 = sha256_file(selection_path)
    selected_hyperparameters = selection["selected_hyperparameters"]

    # Test rows are loaded only after the frozen selection above is verified.
    splits, access = read_final_data(input_path)
    train_rows = splits["train"]
    validation_rows = splits["validation"]
    test_rows = splits["test"]
    final_fit_rows = train_rows + validation_rows

    vectorizer = make_vectorizer()
    final_fit_matrix = vectorizer.fit_transform(texts(final_fit_rows)).tocsr()
    test_matrix = vectorizer.transform(texts(test_rows)).tocsr()
    classifier = make_classifier(selected_hyperparameters)
    fit_classifier(classifier, final_fit_matrix, labels(final_fit_rows))
    test_metrics, predictions, probabilities = evaluate_classifier(
        classifier, test_matrix, test_rows
    )
    test_by_source = evaluate_by_source(test_rows, predictions, probabilities)

    paths = prepare_output_paths(output_dir, overwrite=overwrite)
    model_bundle = {
        "model_id": MODEL_ID,
        "vectorizer": vectorizer,
        "classifier": classifier,
        "metadata": {
            "selection_id": SELECTION_ID,
            "selection_artifact_sha256": selection_sha256,
            "selection_digest": selection["selection_digest"],
            "input_split_sha256": EXPECTED_SPLIT_SHA256,
            "split_version": "group_split_v2",
            "selected_hyperparameters": selected_hyperparameters,
            "threshold": THRESHOLD,
            "label_semantics": LABEL_SEMANTICS,
            "feature_policy": "text_content only",
            "fit_partitions": ["train", "validation"],
            "excluded_partitions": ["auxiliary", "quarantine"],
            "deployment_allowed": False,
        },
    }
    joblib.dump(model_bundle, paths["model"], compress=3)
    write_predictions(paths["test_predictions"], test_rows, predictions, probabilities)
    model_sha256 = sha256_file(paths["model"])
    predictions_sha256 = sha256_file(paths["test_predictions"])

    quality_gates = {
        "input_split_sha256_matches_frozen_v2": sha256_file(input_path)
        == EXPECTED_SPLIT_SHA256,
        "selection_frozen_before_test_load": True,
        "selection_digest_verified": True,
        "test_not_used_for_candidate_selection": selection["selection_policy"][
            "test_used_for_selection"
        ]
        is False,
        "final_fit_uses_train_and_validation_only": len(final_fit_rows) == 4_754,
        "test_rows_evaluated_exact": len(test_rows) == 838,
        "auxiliary_rows_used_zero": access["auxiliary_rows_loaded_for_modeling"] == 0,
        "quarantine_rows_used_zero": access["quarantine_rows_loaded_for_modeling"] == 0,
        "source_dataset_not_in_feature_matrix": True,
        "predictions_cover_test_once": len(predictions) == len(test_rows)
        == len({row["record_id"] for row in test_rows}),
        "all_four_sources_in_test": len(test_by_source) == 4,
        "model_artifact_written": paths["model"].is_file(),
        "test_predictions_written": paths["test_predictions"].is_file(),
    }
    failed = sorted(name for name, passed in quality_gates.items() if not passed)
    if failed:
        raise ValueError("Final baseline quality gates failed: " + ", ".join(failed))

    report = {
        "model_id": MODEL_ID,
        "run_at": run_at,
        "status": "FROZEN_INTERNAL_BASELINE_NOT_FOR_DEPLOYMENT",
        "label_semantics": LABEL_SEMANTICS,
        "selection": {
            "selection_id": selection["selection_id"],
            "selection_file_name": selection_path.name,
            "selection_artifact_sha256": selection_sha256,
            "selection_digest": selection["selection_digest"],
            "selected_candidate_index": selection["selected_candidate_index"],
            "selected_hyperparameters": selected_hyperparameters,
            "selected_validation": selection["selected_validation"],
            "selected_validation_source_summary": selection[
                "selected_validation_source_summary"
            ],
            "test_used_for_selection": False,
        },
        "data": {
            "input_file_name": input_path.name,
            "input_split_sha256": EXPECTED_SPLIT_SHA256,
            "split_version": "group_split_v2",
            "partition_counts": EXPECTED_PARTITION_COUNTS,
            "final_fit_row_count": len(final_fit_rows),
            "test_row_count": len(test_rows),
            "final_fit_source_label_counts": source_label_counts(final_fit_rows),
            "test_source_label_counts": source_label_counts(test_rows),
            "access": access,
        },
        "feature_contract": {
            "predictive_input": ["text_content"],
            "source_dataset_in_feature_matrix": False,
            "split_group_id_in_feature_matrix": False,
            "metadata_in_feature_matrix": False,
            "auxiliary_or_quarantine_rows_used": False,
            "vectorizer_fit_partitions": ["train", "validation"],
            "test_used_only_for_final_evaluation": True,
            "network_operations": 0,
        },
        "vectorizer": {
            **VECTORIZER_CONFIG,
            "vocabulary_size": len(vectorizer.vocabulary_),
            "final_fit_matrix_nnz": int(final_fit_matrix.nnz),
            "test_matrix_nnz": int(test_matrix.nnz),
        },
        "classifier": {
            "type": "LogisticRegression",
            "solver": "liblinear",
            "max_iter": 2_000,
            "random_state": RANDOM_STATE,
            "threshold": THRESHOLD,
            **selected_hyperparameters,
        },
        "test": test_metrics,
        "test_by_source_dataset": test_by_source,
        "test_source_summary": source_summary(test_by_source),
        "top_coefficients": top_coefficients(vectorizer, classifier),
        "artifacts": {
            "model": {
                "file_name": paths["model"].name,
                "sha256": model_sha256,
            },
            "test_predictions": {
                "file_name": paths["test_predictions"].name,
                "sha256": predictions_sha256,
                "row_count": len(test_rows),
            },
        },
        "quality_gates": quality_gates,
        "safety_contract": {
            "raw_files_modified": False,
            "split_file_modified": False,
            "source_labels_changed": 0,
            "network_operations": 0,
            "test_opened_after_selection_frozen": True,
            "deployment_allowed": False,
        },
        "limitations": [
            "This is an internal research test created after group_split_v1 findings were known; it is not external or Gold evaluation.",
            "Mendeley source labels are not regulator-verified investment-scam ground truth.",
            "Known template leakage is controlled, but residual high character similarity remains in some evaluation rows.",
            "The text-only model can encode source/style artifacts and is not suitable for enforcement, blocking, or financial decisions.",
        ],
    }
    paths["results"].write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-at", default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if not args.selection.is_file():
        raise FileNotFoundError(args.selection)
    if args.input.resolve() == args.selection.resolve():
        raise ValueError("Input split and selection artifact must be different files")
    run_at = args.run_at or datetime.now(timezone.utc).isoformat()
    report = evaluate_frozen_selection(
        args.input,
        args.selection,
        args.output_dir,
        run_at=run_at,
        overwrite=args.overwrite,
    )
    print(
        json.dumps(
            {
                "model_id": report["model_id"],
                "status": report["status"],
                "selected_hyperparameters": report["selection"][
                    "selected_hyperparameters"
                ],
                "selection_validation": report["selection"]["selected_validation"],
                "test": report["test"],
                "test_source_summary": report["test_source_summary"],
                "artifacts": report["artifacts"],
                "output_dir": str(args.output_dir),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
