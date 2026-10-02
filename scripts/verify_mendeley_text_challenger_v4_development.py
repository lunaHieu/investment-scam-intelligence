"""Independently verify the rejected V4 train-only OOF semantic challenger."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from generate_mendeley_text_challenger_v4_embeddings import (  # noqa: E402
    EXPECTED_PROTOCOL_SHA256,
    load_json,
    read_train_only,
)
from mendeley_text_baseline_v2_common import sha256_file  # noqa: E402
from run_mendeley_text_challenger_v4_development import (  # noqa: E402
    BASELINE_ID,
    CHALLENGER_ID,
    SELECTION_ID,
    comparison_values,
    development_gate,
    representation_report,
)


EXPECTED_STATUS = "DEVELOPMENT_CHALLENGER_REJECTED_VALIDATION_TEST_EXTERNAL_UNOPENED"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line:
            raise ValueError(f"Blank JSONL line: {line_number}")
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"JSONL line is not an object: {line_number}")
        rows.append(value)
    return rows


def verify(result_path: Path) -> dict[str, Any]:
    result = load_json(result_path)
    errors: list[str] = []
    if result.get("selection_id") != SELECTION_ID:
        errors.append("Unexpected selection ID")
    if result.get("status") != EXPECTED_STATUS:
        errors.append("Unexpected development status")
    if result.get("protocol", {}).get("sha256") != EXPECTED_PROTOCOL_SHA256:
        errors.append("Protocol checksum mismatch")

    input_path = Path(result.get("data", {}).get("input_path", ""))
    if not input_path.is_file() or sha256_file(input_path) != result.get("data", {}).get(
        "input_sha256"
    ):
        errors.append("Split artifact missing or changed")
        train_rows = []
        access = {}
    else:
        train_rows, access = read_train_only(input_path)

    prediction_info = result.get("artifacts", {}).get("development_oof_predictions", {})
    predictions_path = Path(prediction_info.get("path", ""))
    if not predictions_path.is_file() or sha256_file(predictions_path) != prediction_info.get(
        "sha256"
    ):
        errors.append("Prediction artifact missing or changed")
        predictions = []
    else:
        predictions = load_jsonl(predictions_path)

    if len(predictions) != 3916 or len({row.get("record_id") for row in predictions}) != 3916:
        errors.append("Expected 3,916 unique development predictions")
    if any(row.get("partition") != "train" for row in predictions):
        errors.append("Prediction artifact contains a non-train row")
    if any(row.get("stage") != "development_oof" for row in predictions):
        errors.append("Prediction artifact contains a non-OOF stage")
    if {row.get("development_fold") for row in predictions} != {0, 1, 2, 3}:
        errors.append("Prediction artifact does not contain exactly four folds")

    expected_by_id = {row["record_id"]: row for row in train_rows}
    for prediction in predictions:
        expected = expected_by_id.get(prediction.get("record_id"))
        if expected is None:
            errors.append(f"Unknown prediction record: {prediction.get('record_id')}")
            break
        for key in ("split_group_id", "source_dataset"):
            if prediction.get(key) != expected[key]:
                errors.append(f"Prediction {key} mismatch: {prediction.get('record_id')}")
                break
        if prediction.get("source_label") != int(expected["label"]):
            errors.append(f"Prediction label mismatch: {prediction.get('record_id')}")
            break

    group_folds: dict[str, set[int]] = {}
    for row in predictions:
        group_folds.setdefault(str(row.get("split_group_id")), set()).add(
            int(row.get("development_fold", -1))
        )
    if any(len(folds) != 1 for folds in group_folds.values()):
        errors.append("At least one split_group_id crosses OOF folds")

    recomputed_reports = {}
    if predictions and not errors:
        report_rows = [expected_by_id[row["record_id"]] for row in predictions]
        for name, prefix in ((BASELINE_ID, "baseline"), (CHALLENGER_ID, "challenger")):
            predicted = np.asarray(
                [int(row[f"{prefix}_prediction"]) for row in predictions], dtype=np.int64
            )
            probabilities = np.asarray(
                [float(row[f"{prefix}_score_label_1"]) for row in predictions],
                dtype=np.float64,
            )
            recomputed_reports[name] = representation_report(
                report_rows, predicted, probabilities
            )
            stored = result.get("representations", {}).get(name, {}).get("development_oof")
            if recomputed_reports[name] != stored:
                errors.append(f"Stored OOF report does not reproduce: {name}")

    stored_decision = result.get("decision", {})
    independently_verified_failures: list[str] = []
    if len(recomputed_reports) == 2:
        source_delta = float(stored_decision.get("observed", {}).get(
            "source_predictability_macro_f1_delta", 0.0
        ))
        values = comparison_values(
            recomputed_reports[BASELINE_ID],
            recomputed_reports[CHALLENGER_ID],
            source_delta,
        )
        for key in (
            "source_mean_macro_f1_delta",
            "worst_source_macro_f1_delta",
            "pooled_macro_f1_delta",
            "maximum_single_source_macro_f1_decline",
            "per_source_macro_f1_delta",
        ):
            if values[key] != stored_decision.get("observed", {}).get(key):
                errors.append(f"Decision value does not reproduce: {key}")
        thresholds = stored_decision.get("thresholds", {})
        performance_gate_map = {
            "source_mean_macro_f1_delta_minimum": values["source_mean_macro_f1_delta"]
            >= thresholds.get("source_mean_macro_f1_delta_minimum", float("inf")),
            "worst_source_macro_f1_delta_minimum": values["worst_source_macro_f1_delta"]
            >= thresholds.get("worst_source_macro_f1_delta_minimum", float("inf")),
            "pooled_macro_f1_delta_minimum": values["pooled_macro_f1_delta"]
            >= thresholds.get("pooled_macro_f1_delta_minimum", float("inf")),
            "maximum_single_source_macro_f1_decline": values[
                "maximum_single_source_macro_f1_decline"
            ]
            <= thresholds.get("maximum_single_source_macro_f1_decline", float("-inf")),
        }
        independently_verified_failures = sorted(
            name for name, passed in performance_gate_map.items() if not passed
        )
        if len(independently_verified_failures) != 4:
            errors.append("Expected all four prediction-reproducible performance gates to fail")

        shuffle_delta = float(stored_decision.get("observed", {}).get(
            "within_source_label_shuffle_macro_f1_delta", 0.0
        ))
        regenerated = development_gate(values, thresholds, shuffle_delta)
        if regenerated.get("gates") != stored_decision.get("gates"):
            errors.append("Stored gate decisions do not reproduce from observed values")
        if regenerated.get("all_gates_passed") is not False:
            errors.append("Regenerated development decision unexpectedly passes")

    decision_closed = (
        stored_decision.get("all_gates_passed") is False
        and stored_decision.get("selected_variant") == BASELINE_ID
        and stored_decision.get("validation_access_allowed") is False
        and stored_decision.get("validation_opened") is False
        and stored_decision.get("internal_test_allowed") is False
        and stored_decision.get("existing_external_benchmark_allowed") is False
        and stored_decision.get("challenger_model_artifact_allowed") is False
    )
    if not decision_closed:
        errors.append("One or more post-development gates are open")

    quality = result.get("quality_gates", {})
    if not quality or not all(value is True for value in quality.values()):
        errors.append("One or more development quality gates failed")
    safety = result.get("safety_contract", {})
    for key, expected in {
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
    }.items():
        if safety.get(key) != expected:
            errors.append(f"Safety contract mismatch: {key}")
    if access and (
        access.get("validation_text_rows_retained") != 0
        or access.get("validation_labels_accessed") != 0
        or access.get("test_text_rows_retained") != 0
        or access.get("test_labels_accessed") != 0
    ):
        errors.append("Independent train reader retained prohibited partitions")

    unexpected_validation_files = sorted(
        str(path)
        for path in result_path.parent.parent.rglob("*validation*")
        if path.is_file()
    )
    if unexpected_validation_files:
        errors.append("Validation-named artifacts exist under challenger V4 output root")

    return {
        "selection_id": result.get("selection_id"),
        "valid": not errors,
        "status": result.get("status"),
        "prediction_count": len(predictions),
        "unique_group_count": len(group_folds),
        "row_count_by_fold": dict(sorted(Counter(
            row.get("development_fold") for row in predictions
        ).items())),
        "baseline_macro_f1": recomputed_reports.get(BASELINE_ID, {})
        .get("metrics", {})
        .get("macro_f1"),
        "challenger_macro_f1": recomputed_reports.get(CHALLENGER_ID, {})
        .get("metrics", {})
        .get("macro_f1"),
        "independently_verified_failed_performance_gates": independently_verified_failures,
        "all_stored_failed_gates": stored_decision.get("failed_gates", []),
        "validation_opened": False,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.result)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
