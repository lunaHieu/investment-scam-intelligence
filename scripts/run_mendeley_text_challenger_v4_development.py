"""Run the frozen V4 four-fold OOF comparison on train only and gate validation."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import warnings
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.multiclass import OneVsRestClassifier


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from generate_mendeley_text_challenger_v4_embeddings import (  # noqa: E402
    EXPECTED_PROTOCOL_SHA256,
    canonical_digest,
    load_json,
    ordered_input_digest,
    read_train_only,
    validate_protocol,
)
from mendeley_text_baseline_v2_common import (  # noqa: E402
    EXPECTED_SOURCES,
    RANDOM_STATE,
    binary_metrics,
    evaluate_by_source,
    labels,
    make_classifier,
    make_vectorizer,
    sha256_file,
    source_summary,
    texts,
)


SELECTION_ID = "MENDELEY_TEXT_CHALLENGER_V4_DEVELOPMENT_OOF_SELECTION"
BASELINE_ID = "word_1_2"
CHALLENGER_ID = "frozen_e5_small_v2_ffb93f3b"


def assign_development_folds(
    rows: list[dict[str, str]], *, fold_count: int, seed: str
) -> dict[str, int]:
    members: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        members[row["split_group_id"]].append(row)
    strata: dict[tuple[str, str], list[str]] = defaultdict(list)
    for group_id, group_rows in members.items():
        sources = {row["source_dataset"] for row in group_rows}
        group_labels = {row["label"] for row in group_rows}
        if len(sources) != 1 or len(group_labels) != 1:
            raise ValueError(f"Development group mixes source or label: {group_id}")
        strata[(next(iter(sources)), next(iter(group_labels)))].append(group_id)
    mapping: dict[str, int] = {}
    for key in sorted(strata):
        ordered = sorted(
            strata[key],
            key=lambda group_id: hashlib.sha256(
                f"{seed}|{group_id}".encode("utf-8")
            ).hexdigest(),
        )
        for index, group_id in enumerate(ordered):
            mapping[group_id] = index % fold_count
    if len(mapping) != len(members):
        raise ValueError("Not every development group received one fold")
    return mapping


def shuffled_labels_within_source(
    rows: list[dict[str, str]], *, seed: int
) -> np.ndarray:
    result = labels(rows).copy()
    rng = np.random.default_rng(seed)
    for source in sorted({row["source_dataset"] for row in rows}):
        indices = np.asarray(
            [index for index, row in enumerate(rows) if row["source_dataset"] == source],
            dtype=np.int64,
        )
        values = result[indices].copy()
        rng.shuffle(values)
        result[indices] = values
    return result


def fit_binary(matrix, truth: np.ndarray) -> LogisticRegression:
    classifier = make_classifier({"C": 2.0, "class_weight": None})
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        classifier.fit(matrix, truth)
    return classifier


def fit_source_classifier(matrix, rows: list[dict[str, str]]) -> OneVsRestClassifier:
    targets = np.asarray([row["source_dataset"] for row in rows], dtype=object)
    estimator = LogisticRegression(
        C=2.0,
        class_weight=None,
        solver="liblinear",
        max_iter=2000,
        random_state=RANDOM_STATE,
    )
    classifier = OneVsRestClassifier(estimator)
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        classifier.fit(matrix, targets)
    return classifier


def evaluate_fold(
    fit_matrix,
    evaluation_matrix,
    fit_rows: list[dict[str, str]],
    evaluation_rows: list[dict[str, str]],
    shuffled_truth: np.ndarray,
) -> dict[str, np.ndarray]:
    classifier = fit_binary(fit_matrix, labels(fit_rows))
    probabilities = classifier.predict_proba(evaluation_matrix)[:, 1]
    predictions = (probabilities >= 0.5).astype(np.int64)
    source_classifier = fit_source_classifier(fit_matrix, fit_rows)
    source_predictions = source_classifier.predict(evaluation_matrix)
    shuffled_classifier = fit_binary(fit_matrix, shuffled_truth)
    shuffled_predictions = shuffled_classifier.predict(evaluation_matrix).astype(np.int64)
    return {
        "predictions": predictions,
        "probabilities": probabilities,
        "source_predictions": source_predictions,
        "shuffled_predictions": shuffled_predictions,
    }


def representation_report(
    rows: list[dict[str, str]], predictions: np.ndarray, probabilities: np.ndarray
) -> dict[str, Any]:
    by_source = evaluate_by_source(rows, predictions, probabilities)
    return {
        "metrics": binary_metrics(labels(rows), predictions, probabilities),
        "by_source_dataset": by_source,
        "source_summary": source_summary(by_source),
    }


def source_metric(rows: list[dict[str, str]], predictions: np.ndarray) -> dict[str, Any]:
    truth = np.asarray([row["source_dataset"] for row in rows], dtype=object)
    majority = Counter(truth).most_common(1)[0][0]
    majority_predictions = np.full(len(truth), majority, dtype=object)
    return {
        "macro_f1": round(
            float(f1_score(truth, predictions, average="macro", zero_division=0)), 6
        ),
        "majority_source_macro_f1": round(
            float(f1_score(truth, majority_predictions, average="macro", zero_division=0)),
            6,
        ),
        "source_dataset_used_as_diagnostic_target_only": True,
    }


def comparison_values(
    baseline: dict[str, Any], challenger: dict[str, Any], source_delta: float
) -> dict[str, Any]:
    per_source = {
        source: round(
            challenger["by_source_dataset"][source]["macro_f1"]
            - baseline["by_source_dataset"][source]["macro_f1"],
            6,
        )
        for source in sorted(baseline["by_source_dataset"])
    }
    return {
        "source_mean_macro_f1_delta": round(
            challenger["source_summary"]["unweighted_mean_macro_f1_across_sources"]
            - baseline["source_summary"]["unweighted_mean_macro_f1_across_sources"],
            6,
        ),
        "worst_source_macro_f1_delta": round(
            challenger["source_summary"]["worst_source_macro_f1"]
            - baseline["source_summary"]["worst_source_macro_f1"],
            6,
        ),
        "pooled_macro_f1_delta": round(
            challenger["metrics"]["macro_f1"] - baseline["metrics"]["macro_f1"], 6
        ),
        "maximum_single_source_macro_f1_decline": round(
            max(0.0, max(-value for value in per_source.values())), 6
        ),
        "source_predictability_macro_f1_delta": round(float(source_delta), 6),
        "per_source_macro_f1_delta": per_source,
    }


def development_gate(
    values: dict[str, Any], thresholds: dict[str, float], shuffle_delta: float
) -> dict[str, Any]:
    observed = dict(values)
    observed["within_source_label_shuffle_macro_f1_delta"] = round(
        float(shuffle_delta), 6
    )
    gates = {
        "source_mean_macro_f1_delta_minimum": values["source_mean_macro_f1_delta"]
        >= thresholds["source_mean_macro_f1_delta_minimum"],
        "worst_source_macro_f1_delta_minimum": values["worst_source_macro_f1_delta"]
        >= thresholds["worst_source_macro_f1_delta_minimum"],
        "pooled_macro_f1_delta_minimum": values["pooled_macro_f1_delta"]
        >= thresholds["pooled_macro_f1_delta_minimum"],
        "maximum_single_source_macro_f1_decline": values[
            "maximum_single_source_macro_f1_decline"
        ]
        <= thresholds["maximum_single_source_macro_f1_decline"],
        "source_predictability_macro_f1_delta_maximum": values[
            "source_predictability_macro_f1_delta"
        ]
        <= thresholds["source_predictability_macro_f1_delta_maximum"],
        "within_source_label_shuffle_macro_f1_delta_maximum": observed[
            "within_source_label_shuffle_macro_f1_delta"
        ]
        <= thresholds["within_source_label_shuffle_macro_f1_delta_maximum"],
    }
    return {
        "thresholds": thresholds,
        "observed": observed,
        "gates": gates,
        "failed_gates": sorted(name for name, passed in gates.items() if not passed),
        "all_gates_passed": all(gates.values()),
    }


def load_verified_embeddings(
    embeddings_path: Path,
    metadata_path: Path,
    protocol: dict[str, Any],
    rows: list[dict[str, str]],
) -> tuple[np.ndarray, dict[str, Any]]:
    metadata = load_json(metadata_path)
    if metadata.get("status") != "FROZEN_TRAIN_ONLY_EMBEDDINGS_VALIDATED":
        raise ValueError("Embedding metadata is not frozen and validated")
    if metadata.get("protocol", {}).get("sha256") != EXPECTED_PROTOCOL_SHA256:
        raise ValueError("Embedding metadata protocol hash mismatch")
    artifact = metadata.get("artifacts", {}).get("embedding_cache", {})
    if Path(artifact.get("path", "")) != embeddings_path:
        raise ValueError("Embedding cache path mismatch")
    if sha256_file(embeddings_path) != artifact.get("sha256"):
        raise ValueError("Embedding cache SHA-256 mismatch")
    prefix = protocol["text_to_embedding_contract"]["prefix"]
    input_digest = ordered_input_digest(rows, prefix)
    if input_digest != metadata.get("input", {}).get(
        "ordered_record_id_and_prefixed_text_sha256"
    ):
        raise ValueError("Embedding ordered-input digest mismatch")
    expected_key = {
        **metadata["cache_key"],
        "ordered_record_id_and_prefixed_text_sha256": input_digest,
    }
    if canonical_digest(expected_key) != metadata.get("cache_key_sha256"):
        raise ValueError("Embedding cache-key digest mismatch")

    with np.load(embeddings_path, allow_pickle=False) as cache:
        record_ids = cache["record_id"].astype(str)
        embeddings = cache["embedding"].astype(np.float32, copy=False)
    expected_ids = np.asarray([row["record_id"] for row in rows], dtype=str)
    if not np.array_equal(record_ids, expected_ids):
        raise ValueError("Embedding record order does not match sorted train records")
    if embeddings.shape != (3916, 384):
        raise ValueError(f"Unexpected embedding shape: {embeddings.shape}")
    if not np.isfinite(embeddings).all():
        raise ValueError("Embedding cache contains non-finite values")
    if float(np.max(np.abs(np.linalg.norm(embeddings, axis=1) - 1.0))) > 1e-5:
        raise ValueError("Embedding cache rows are not L2 normalized")
    return embeddings, metadata


def prepare_outputs(output_dir: Path) -> tuple[Path, Path]:
    result_path = output_dir / "text_challenger_v4_development_oof_result.json"
    predictions_path = output_dir / "text_challenger_v4_development_oof_predictions.jsonl"
    for path in (result_path, predictions_path):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite frozen development output: {path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    return result_path, predictions_path


def write_predictions(
    path: Path,
    rows: list[dict[str, str]],
    fold_by_group: dict[str, int],
    baseline: dict[str, np.ndarray],
    challenger: dict[str, np.ndarray],
) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for index, row in enumerate(rows):
            value = {
                "record_id": row["record_id"],
                "stage": "development_oof",
                "partition": "train",
                "split_group_id": row["split_group_id"],
                "source_dataset": row["source_dataset"],
                "source_label": int(row["label"]),
                "development_fold": int(fold_by_group[row["split_group_id"]]),
                "baseline_prediction": int(baseline["predictions"][index]),
                "baseline_score_label_1": round(float(baseline["probabilities"][index]), 10),
                "challenger_prediction": int(challenger["predictions"][index]),
                "challenger_score_label_1": round(
                    float(challenger["probabilities"][index]), 10
                ),
            }
            handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--baseline-registry", type=Path, required=True)
    parser.add_argument("--embeddings", type=Path, required=True)
    parser.add_argument("--embedding-metadata", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-at", required=True)
    args = parser.parse_args()

    protocol = validate_protocol(args.protocol, args.input)
    if sha256_file(args.baseline_registry) != protocol["data_contract"][
        "baseline_registry_sha256"
    ]:
        raise ValueError("Baseline registry SHA-256 mismatch")
    result_path, predictions_path = prepare_outputs(args.output_dir)
    rows, access = read_train_only(args.input)
    embeddings, embedding_metadata = load_verified_embeddings(
        args.embeddings, args.embedding_metadata, protocol, rows
    )

    design = protocol["development_design"]
    fold_by_group = assign_development_folds(
        rows, fold_count=int(design["fold_count"]), seed=design["fold_seed"]
    )
    oof = {
        name: {
            "predictions": np.empty(len(rows), dtype=np.int64),
            "probabilities": np.empty(len(rows), dtype=np.float64),
            "source_predictions": np.empty(len(rows), dtype=object),
            "shuffled_predictions": np.empty(len(rows), dtype=np.int64),
            "folds": [],
        }
        for name in (BASELINE_ID, CHALLENGER_ID)
    }

    for fold in range(int(design["fold_count"])):
        fit_indices = np.asarray(
            [
                index
                for index, row in enumerate(rows)
                if fold_by_group[row["split_group_id"]] != fold
            ],
            dtype=np.int64,
        )
        evaluation_indices = np.asarray(
            [
                index
                for index, row in enumerate(rows)
                if fold_by_group[row["split_group_id"]] == fold
            ],
            dtype=np.int64,
        )
        fit_rows = [rows[int(index)] for index in fit_indices]
        evaluation_rows = [rows[int(index)] for index in evaluation_indices]
        if {row["source_dataset"] for row in fit_rows} != EXPECTED_SOURCES:
            raise ValueError(f"Fold {fold} fit lacks an expected source")
        if {row["source_dataset"] for row in evaluation_rows} != EXPECTED_SOURCES:
            raise ValueError(f"Fold {fold} evaluation lacks an expected source")
        shuffled_truth = shuffled_labels_within_source(
            fit_rows, seed=int(protocol["diagnostics"]["shuffle_seed"]) + fold
        )

        vectorizer = make_vectorizer()
        baseline_fit = vectorizer.fit_transform(texts(fit_rows)).tocsr()
        baseline_evaluation = vectorizer.transform(texts(evaluation_rows)).tocsr()
        matrices = {
            BASELINE_ID: (baseline_fit, baseline_evaluation),
            CHALLENGER_ID: (embeddings[fit_indices], embeddings[evaluation_indices]),
        }
        for name, (fit_matrix, evaluation_matrix) in matrices.items():
            evaluated = evaluate_fold(
                fit_matrix,
                evaluation_matrix,
                fit_rows,
                evaluation_rows,
                shuffled_truth,
            )
            for key in (
                "predictions",
                "probabilities",
                "source_predictions",
                "shuffled_predictions",
            ):
                oof[name][key][evaluation_indices] = evaluated[key]
            diagnostic = {
                "fold": fold,
                "fit_rows": int(len(fit_indices)),
                "evaluation_rows": int(len(evaluation_indices)),
                "feature_count": int(fit_matrix.shape[1]),
            }
            if hasattr(fit_matrix, "nnz"):
                diagnostic["fit_matrix_nnz"] = int(fit_matrix.nnz)
                diagnostic["evaluation_matrix_nnz"] = int(evaluation_matrix.nnz)
            oof[name]["folds"].append(diagnostic)
        print(
            json.dumps({
                "event": "oof_fold_complete",
                "fold": fold,
                "fit_rows": int(len(fit_indices)),
                "evaluation_rows": int(len(evaluation_indices)),
            }),
            flush=True,
        )

    reports: dict[str, Any] = {}
    diagnostics: dict[str, Any] = {}
    truth = labels(rows)
    for name in (BASELINE_ID, CHALLENGER_ID):
        reports[name] = representation_report(
            rows, oof[name]["predictions"], oof[name]["probabilities"]
        )
        diagnostics[name] = {
            "source_predictability": source_metric(rows, oof[name]["source_predictions"]),
            "within_source_label_shuffle": {
                "macro_f1": round(
                    float(
                        f1_score(
                            truth,
                            oof[name]["shuffled_predictions"],
                            average="macro",
                            zero_division=0,
                        )
                    ),
                    6,
                ),
                "same_shuffled_training_labels_used_for_both_representations": True,
            },
            "folds": oof[name]["folds"],
        }

    values = comparison_values(
        reports[BASELINE_ID],
        reports[CHALLENGER_ID],
        diagnostics[CHALLENGER_ID]["source_predictability"]["macro_f1"]
        - diagnostics[BASELINE_ID]["source_predictability"]["macro_f1"],
    )
    decision = development_gate(
        values,
        protocol["selection_policy"]["development_oof_gates"],
        diagnostics[CHALLENGER_ID]["within_source_label_shuffle"]["macro_f1"]
        - diagnostics[BASELINE_ID]["within_source_label_shuffle"]["macro_f1"],
    )

    group_fold_counts = Counter(fold_by_group.values())
    row_fold_counts = Counter(fold_by_group[row["split_group_id"]] for row in rows)
    quality_gates = {
        "protocol_hash_verified": sha256_file(args.protocol) == EXPECTED_PROTOCOL_SHA256,
        "split_hash_verified": sha256_file(args.input)
        == protocol["data_contract"]["split_sha256"],
        "baseline_registry_hash_verified": sha256_file(args.baseline_registry)
        == protocol["data_contract"]["baseline_registry_sha256"],
        "embedding_cache_hash_verified": sha256_file(args.embeddings)
        == embedding_metadata["artifacts"]["embedding_cache"]["sha256"],
        "train_rows_exact": len(rows) == 3916,
        "development_groups_assigned_once": len(fold_by_group) == 3783,
        "all_four_sources_present": {row["source_dataset"] for row in rows}
        == EXPECTED_SOURCES,
        "one_challenger_only": set(oof) == {BASELINE_ID, CHALLENGER_ID},
        "validation_text_rows_retained_zero": access["validation_text_rows_retained"] == 0,
        "validation_labels_accessed_zero": access["validation_labels_accessed"] == 0,
        "test_text_rows_retained_zero": access["test_text_rows_retained"] == 0,
        "test_labels_accessed_zero": access["test_labels_accessed"] == 0,
        "external_benchmark_rows_loaded_zero": True,
        "model_artifact_created_false": True,
    }
    failed_quality = sorted(name for name, passed in quality_gates.items() if not passed)
    if failed_quality:
        raise ValueError("V4 development quality gates failed: " + ", ".join(failed_quality))

    write_predictions(
        predictions_path,
        rows,
        fold_by_group,
        oof[BASELINE_ID],
        oof[CHALLENGER_ID],
    )
    result = {
        "selection_id": SELECTION_ID,
        "run_at": args.run_at,
        "status": (
            "DEVELOPMENT_GATES_PASSED_VALIDATION_AUTHORIZED_NOT_OPENED"
            if decision["all_gates_passed"]
            else "DEVELOPMENT_CHALLENGER_REJECTED_VALIDATION_TEST_EXTERNAL_UNOPENED"
        ),
        "protocol": {
            "path": str(args.protocol),
            "sha256": sha256_file(args.protocol),
        },
        "data": {
            "input_path": str(args.input),
            "input_sha256": sha256_file(args.input),
            "partition": "train",
            "row_count": len(rows),
            "group_count": len(fold_by_group),
            "group_count_by_fold": dict(sorted(group_fold_counts.items())),
            "row_count_by_fold": dict(sorted(row_fold_counts.items())),
            "access": access,
        },
        "embedding_input": {
            "path": str(args.embeddings),
            "sha256": sha256_file(args.embeddings),
            "metadata_path": str(args.embedding_metadata),
            "metadata_sha256": sha256_file(args.embedding_metadata),
            "shape": [3916, 384],
        },
        "representations": {
            BASELINE_ID: {
                "development_oof": reports[BASELINE_ID],
                "diagnostics": diagnostics[BASELINE_ID],
            },
            CHALLENGER_ID: {
                "development_oof": reports[CHALLENGER_ID],
                "diagnostics": diagnostics[CHALLENGER_ID],
            },
        },
        "decision": {
            **decision,
            "selected_variant": CHALLENGER_ID
            if decision["all_gates_passed"]
            else BASELINE_ID,
            "validation_access_allowed": decision["all_gates_passed"],
            "validation_opened": False,
            "internal_test_allowed": False,
            "existing_external_benchmark_allowed": False,
            "challenger_model_artifact_allowed": False,
        },
        "quality_gates": quality_gates,
        "safety_contract": {
            "network_operations": 0,
            "embedding_scope": "train only",
            "binary_classifier_fit_calls": 16,
            "source_diagnostic_fit_calls": 8,
            "total_fit_calls": 24,
            "validation_rows_retained": 0,
            "validation_labels_accessed": 0,
            "validation_scoring_operations": 0,
            "internal_test_rows_retained": 0,
            "internal_test_labels_accessed": 0,
            "external_benchmark_rows_loaded": 0,
            "auxiliary_rows_used": 0,
            "quarantine_rows_used": 0,
            "threshold_changes": 0,
            "model_artifact_created": False,
            "deployment_allowed": False,
        },
        "artifacts": {
            "development_oof_predictions": {
                "path": str(predictions_path),
                "sha256": sha256_file(predictions_path),
                "record_count": len(rows),
            }
        },
    }
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "result": str(result_path),
        "result_sha256": sha256_file(result_path),
        "predictions": str(predictions_path),
        "predictions_sha256": sha256_file(predictions_path),
        "status": result["status"],
        "baseline": reports[BASELINE_ID],
        "challenger": reports[CHALLENGER_ID],
        "decision": result["decision"],
        "validation_opened": False,
        "test_opened": False,
        "external_benchmark_opened": False,
    }, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
