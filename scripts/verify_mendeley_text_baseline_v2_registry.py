"""Verify the frozen Mendeley text baseline V2 and all local artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np

from mendeley_text_baseline_v2_common import (
    CANDIDATES,
    EXPECTED_PARTITION_COUNTS,
    EXPECTED_SPLIT_SHA256,
    MODEL_ID,
    SELECTION_ID,
    THRESHOLD,
    binary_metrics,
    candidate_score,
    evaluate_by_source,
    read_final_data,
    sha256_file,
    source_summary,
    texts,
    validate_frozen_selection,
)


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_close(actual: float, expected: float, label: str, tolerance=1e-9) -> None:
    if abs(float(actual) - float(expected)) > tolerance:
        raise ValueError(f"{label} mismatch: {actual} != {expected}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        type=Path,
        default=ROOT / "registry" / "models" / "text_baseline_v2.json",
    )
    args = parser.parse_args()
    registry = load_json(args.registry)
    if registry["model_id"] != MODEL_ID:
        raise ValueError("Unexpected model_id")
    if registry["status"] != "FROZEN_INTERNAL_BASELINE_NOT_FOR_DEPLOYMENT":
        raise ValueError("Model registry is not frozen")
    if registry["data_contract"]["split_version"] != "group_split_v2":
        raise ValueError("Model is not bound to group_split_v2")
    if registry["data_contract"]["partition_counts"] != EXPECTED_PARTITION_COUNTS:
        raise ValueError("Registry partition counts mismatch")

    artifacts = {artifact["role"]: artifact for artifact in registry["artifacts"]}
    expected_roles = {
        "group_split_dataset",
        "validation_selection",
        "model",
        "results",
        "test_predictions",
    }
    if set(artifacts) != expected_roles:
        raise ValueError("Artifact role set mismatch")
    paths = {}
    for role, artifact in artifacts.items():
        path = Path(artifact["path"])
        if not path.is_file():
            raise FileNotFoundError(path)
        observed = sha256_file(path)
        if observed != artifact["sha256"]:
            raise ValueError(f"SHA-256 mismatch for {role}: {observed}")
        paths[role] = path
    if artifacts["group_split_dataset"]["sha256"] != EXPECTED_SPLIT_SHA256:
        raise ValueError("Frozen split hash mismatch")

    selection = load_json(paths["validation_selection"])
    validate_frozen_selection(selection, paths["validation_selection"])
    if not all(selection["quality_gates"].values()):
        raise ValueError("Validation selection has a failed quality gate")
    if selection["predeclared_candidates"] != [dict(value) for value in CANDIDATES]:
        raise ValueError("Selection candidate grid mismatch")
    winner = max(
        selection["candidate_results"],
        key=lambda report: candidate_score(report, report["candidate_index"]),
    )
    if winner["candidate_index"] != selection["selected_candidate_index"]:
        raise ValueError("Selection winner mismatch")
    if winner["hyperparameters"] != selection["selected_hyperparameters"]:
        raise ValueError("Selection hyperparameter mismatch")
    if any("test" in candidate for candidate in selection["candidate_results"]):
        raise ValueError("Validation candidate contains test metrics")

    results = load_json(paths["results"])
    if results["model_id"] != MODEL_ID or results["status"] != registry["status"]:
        raise ValueError("Results model/status mismatch")
    if results["selection"]["selection_id"] != SELECTION_ID:
        raise ValueError("Results selection_id mismatch")
    if results["selection"]["selection_artifact_sha256"] != artifacts[
        "validation_selection"
    ]["sha256"]:
        raise ValueError("Results selection artifact hash mismatch")
    if results["selection"]["selection_digest"] != selection["selection_digest"]:
        raise ValueError("Results selection digest mismatch")
    if results["selection"]["selected_hyperparameters"] != selection[
        "selected_hyperparameters"
    ]:
        raise ValueError("Results selected hyperparameters mismatch")
    if results["selection"]["test_used_for_selection"] is not False:
        raise ValueError("Results claim test was used for selection")
    if not all(results["quality_gates"].values()):
        raise ValueError("Results contain a failed quality gate")
    if results["feature_contract"]["auxiliary_or_quarantine_rows_used"] is not False:
        raise ValueError("Excluded roles entered model workflow")
    if results["feature_contract"]["predictive_input"] != ["text_content"]:
        raise ValueError("Predictive feature contract mismatch")
    if datetime.fromisoformat(selection["run_at"]) >= datetime.fromisoformat(results["run_at"]):
        raise ValueError("Selection was not timestamped before test evaluation")

    model = joblib.load(paths["model"])
    if model["model_id"] != MODEL_ID:
        raise ValueError("Model bundle ID mismatch")
    metadata = model["metadata"]
    if metadata["selection_artifact_sha256"] != artifacts["validation_selection"]["sha256"]:
        raise ValueError("Model bundle selection hash mismatch")
    if metadata["selection_digest"] != selection["selection_digest"]:
        raise ValueError("Model bundle selection digest mismatch")
    if metadata["selected_hyperparameters"] != selection["selected_hyperparameters"]:
        raise ValueError("Model bundle hyperparameters mismatch")
    if metadata["fit_partitions"] != ["train", "validation"]:
        raise ValueError("Model bundle fit partitions mismatch")
    if metadata["excluded_partitions"] != ["auxiliary", "quarantine"]:
        raise ValueError("Model bundle excluded partitions mismatch")
    classifier = model["classifier"]
    vectorizer = model["vectorizer"]
    selected = selection["selected_hyperparameters"]
    assert_close(classifier.C, selected["C"], "classifier C")
    if classifier.class_weight != selected["class_weight"]:
        raise ValueError("classifier class_weight mismatch")
    if classifier.solver != "liblinear":
        raise ValueError("classifier solver mismatch")
    if classifier.coef_.shape[1] != len(vectorizer.vocabulary_):
        raise ValueError("Model coefficient/vocabulary mismatch")

    splits, access = read_final_data(paths["group_split_dataset"])
    if access["auxiliary_rows_loaded_for_modeling"] != 0 or access[
        "quarantine_rows_loaded_for_modeling"
    ] != 0:
        raise ValueError("Excluded rows loaded for verification modeling")
    test_rows = splits["test"]
    test_matrix = vectorizer.transform(texts(test_rows)).tocsr()
    recomputed_probabilities = classifier.predict_proba(test_matrix)[:, 1]
    recomputed_predictions = (recomputed_probabilities >= THRESHOLD).astype(np.int64)

    prediction_records = []
    with paths["test_predictions"].open(encoding="utf-8") as handle:
        for line in handle:
            prediction_records.append(json.loads(line))
    if len(prediction_records) != 838:
        raise ValueError("Test prediction row count mismatch")
    if len({record["record_id"] for record in prediction_records}) != 838:
        raise ValueError("Test prediction record IDs are not unique")
    test_by_id = {row["record_id"]: row for row in test_rows}
    if {record["record_id"] for record in prediction_records} != set(test_by_id):
        raise ValueError("Prediction/test ID coverage mismatch")
    stored_predictions = []
    stored_probabilities = []
    for index, record in enumerate(prediction_records):
        source = test_by_id[record["record_id"]]
        if record["partition"] != "test":
            raise ValueError("Non-test prediction record")
        if record["source_dataset"] != source["source_dataset"]:
            raise ValueError("Prediction source mismatch")
        if record["source_label"] != int(source["label"]):
            raise ValueError("Prediction source label mismatch")
        if record["split_group_id"] != source["split_group_id"]:
            raise ValueError("Prediction split group mismatch")
        if record["predicted_label"] != int(recomputed_predictions[index]):
            raise ValueError("Stored prediction does not match model")
        assert_close(
            record["score_label_1"],
            recomputed_probabilities[index],
            "stored probability",
            tolerance=5e-10,
        )
        stored_predictions.append(record["predicted_label"])
        stored_probabilities.append(record["score_label_1"])
    truth = np.asarray([int(row["label"]) for row in test_rows], dtype=np.int64)
    stored_predictions_array = np.asarray(stored_predictions, dtype=np.int64)
    stored_probabilities_array = np.asarray(stored_probabilities, dtype=np.float64)
    recomputed_metrics = binary_metrics(
        truth, stored_predictions_array, stored_probabilities_array
    )
    if recomputed_metrics != results["test"]:
        raise ValueError("Recomputed pooled test metrics mismatch")
    recomputed_by_source = evaluate_by_source(
        test_rows, stored_predictions_array, stored_probabilities_array
    )
    if recomputed_by_source != results["test_by_source_dataset"]:
        raise ValueError("Recomputed source test metrics mismatch")
    if source_summary(recomputed_by_source) != results["test_source_summary"]:
        raise ValueError("Recomputed source summary mismatch")

    if results["artifacts"]["model"]["sha256"] != artifacts["model"]["sha256"]:
        raise ValueError("Results/registry model hash mismatch")
    if results["artifacts"]["test_predictions"]["sha256"] != artifacts[
        "test_predictions"
    ]["sha256"]:
        raise ValueError("Results/registry prediction hash mismatch")
    if registry["metrics"]["test"] != results["test"]:
        raise ValueError("Registry/results test metrics mismatch")
    if registry["metrics"]["test_source_summary"] != results["test_source_summary"]:
        raise ValueError("Registry/results source summary mismatch")
    safety = registry["safety_contract"]
    if (
        safety["raw_files_modified"] is not False
        or safety["split_file_modified"] is not False
        or safety["network_operations"] != 0
        or safety["test_used_for_selection"] is not False
        or safety["deployment_allowed"] is not False
    ):
        raise ValueError("Registry safety contract mismatch")

    print(
        "Mendeley text baseline V2 valid: selection frozen before test; "
        "4,754 train+validation rows fit, 838 test predictions reproduced; "
        f"test Macro-F1={results['test']['macro_f1']:.6f}, "
        f"worst-source Macro-F1={results['test_source_summary']['worst_source_macro_f1']:.6f}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
