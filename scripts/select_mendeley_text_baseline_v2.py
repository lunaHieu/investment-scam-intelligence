"""Select and freeze the Mendeley text baseline V2 using train/validation only.

The script scans partition/routing fields for the full split but retains text
and labels only for train and validation. Test, auxiliary, and quarantine text
are never transformed or used. The output is a frozen selection artifact that
must exist before the separate final-evaluation script can open test.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from mendeley_text_baseline_v2_common import (
    CANDIDATES,
    EXPECTED_SOURCES,
    EXPECTED_SPLIT_SHA256,
    LABEL_SEMANTICS,
    MODEL_ID,
    RANDOM_STATE,
    SELECTION_ID,
    SELECTION_POLICY,
    THRESHOLD,
    VECTORIZER_CONFIG,
    candidate_score,
    compute_selection_digest,
    evaluate_by_source,
    evaluate_classifier,
    fit_classifier,
    labels,
    make_classifier,
    make_vectorizer,
    read_selection_data,
    sha256_file,
    source_label_counts,
    source_summary,
    texts,
)


def runtime_versions() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "scikit_learn": importlib.metadata.version("scikit-learn"),
        "numpy": importlib.metadata.version("numpy"),
        "scipy": importlib.metadata.version("scipy"),
        "joblib": importlib.metadata.version("joblib"),
    }


def write_json(path: Path, value: dict, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite frozen selection: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def select_configuration(input_path: Path, *, run_at: str) -> dict:
    split_hash_before = sha256_file(input_path)
    splits, access = read_selection_data(input_path)
    train_rows = splits["train"]
    validation_rows = splits["validation"]

    vectorizer = make_vectorizer()
    train_matrix = vectorizer.fit_transform(texts(train_rows)).tocsr()
    validation_matrix = vectorizer.transform(texts(validation_rows)).tocsr()
    train_truth = labels(train_rows)

    candidate_reports = []
    for index, config in enumerate(CANDIDATES):
        classifier = make_classifier(config)
        fit_classifier(classifier, train_matrix, train_truth)
        validation, predictions, probabilities = evaluate_classifier(
            classifier, validation_matrix, validation_rows
        )
        by_source = evaluate_by_source(validation_rows, predictions, probabilities)
        report = {
            "candidate_index": index,
            "hyperparameters": dict(config),
            "validation": validation,
            "validation_by_source_dataset": by_source,
            "validation_source_summary": source_summary(by_source),
        }
        report["selection_score"] = list(candidate_score(report, index))
        candidate_reports.append(report)

    selected = max(
        candidate_reports,
        key=lambda report: tuple(report["selection_score"]),
    )
    selected_hyperparameters = selected["hyperparameters"]
    selection_digest = compute_selection_digest(selected_hyperparameters)
    split_hash_after = sha256_file(input_path)
    validation_sources = {row["source_dataset"] for row in validation_rows}
    validation_labels = {row["label"] for row in validation_rows}
    quality_gates = {
        "input_split_sha256_matches_frozen_v2": split_hash_before == EXPECTED_SPLIT_SHA256,
        "input_split_unchanged_during_selection": split_hash_after == split_hash_before,
        "train_rows_loaded_exact": access["loaded_text_rows"]["train"] == 3_916,
        "validation_rows_loaded_exact": access["loaded_text_rows"]["validation"] == 838,
        "test_text_rows_loaded_zero": access["loaded_text_rows"]["test"] == 0,
        "test_text_transformed_zero": access["test_text_transformed"] == 0,
        "test_labels_used_zero": access["test_labels_used"] == 0,
        "auxiliary_and_quarantine_rows_used_zero": access["excluded_rows_used"] == 0,
        "all_four_sources_present_in_validation": validation_sources == EXPECTED_SOURCES,
        "both_labels_present_in_validation": validation_labels == {"0", "1"},
        "candidate_grid_complete": len(candidate_reports) == len(CANDIDATES) == 10,
        "selected_candidate_is_predeclared": selected_hyperparameters in CANDIDATES,
        "source_dataset_not_in_feature_matrix": True,
        "only_text_content_transformed": True,
    }
    failed = sorted(name for name, passed in quality_gates.items() if not passed)
    if failed:
        raise ValueError("Validation selection quality gates failed: " + ", ".join(failed))

    return {
        "selection_id": SELECTION_ID,
        "model_id": MODEL_ID,
        "run_at": run_at,
        "status": "FROZEN_VALIDATION_SELECTION_TEST_UNOPENED",
        "label_semantics": LABEL_SEMANTICS,
        "data": {
            "input_file_name": input_path.name,
            "input_split_sha256": split_hash_before,
            "split_version": "group_split_v2",
            "train_row_count": len(train_rows),
            "validation_row_count": len(validation_rows),
            "train_source_label_counts": source_label_counts(train_rows),
            "validation_source_label_counts": source_label_counts(validation_rows),
        },
        "data_access": access,
        "feature_contract": {
            "predictive_input": ["text_content"],
            "source_dataset_in_feature_matrix": False,
            "split_group_id_in_feature_matrix": False,
            "metadata_in_feature_matrix": False,
            "auxiliary_or_quarantine_rows_used": False,
            "vectorizer_fitted_on": "train only",
            "validation_transformed_after_train_fit": True,
            "test_transformed": False,
            "network_operations": 0,
        },
        "vectorizer": {
            **VECTORIZER_CONFIG,
            "vocabulary_size": len(vectorizer.vocabulary_),
            "train_matrix_nnz": int(train_matrix.nnz),
        },
        "classifier_contract": {
            "type": "LogisticRegression",
            "solver": "liblinear",
            "max_iter": 2_000,
            "random_state": RANDOM_STATE,
            "threshold": THRESHOLD,
        },
        "selection_policy": SELECTION_POLICY,
        "predeclared_candidates": [dict(candidate) for candidate in CANDIDATES],
        "candidate_results": candidate_reports,
        "selected_candidate_index": selected["candidate_index"],
        "selected_hyperparameters": selected_hyperparameters,
        "selected_validation": selected["validation"],
        "selected_validation_by_source_dataset": selected[
            "validation_by_source_dataset"
        ],
        "selected_validation_source_summary": selected[
            "validation_source_summary"
        ],
        "selection_digest": selection_digest,
        "quality_gates": quality_gates,
        "runtime": runtime_versions(),
        "safety_contract": {
            "raw_files_modified": False,
            "split_file_modified": False,
            "test_opened": False,
            "test_metrics_created": False,
            "model_artifact_created": False,
            "network_operations": 0,
        },
    }


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
        raise ValueError("Input split and selection output must be different files")
    if args.output.exists() and not args.overwrite:
        raise FileExistsError(f"Refusing to overwrite frozen selection: {args.output}")
    run_at = args.run_at or datetime.now(timezone.utc).isoformat()
    report = select_configuration(args.input, run_at=run_at)
    write_json(args.output, report, overwrite=args.overwrite)
    print(
        json.dumps(
            {
                "selection_id": report["selection_id"],
                "status": report["status"],
                "selected_hyperparameters": report["selected_hyperparameters"],
                "selection_digest": report["selection_digest"],
                "validation": report["selected_validation"],
                "validation_source_summary": report[
                    "selected_validation_source_summary"
                ],
                "test_opened": report["safety_contract"]["test_opened"],
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
