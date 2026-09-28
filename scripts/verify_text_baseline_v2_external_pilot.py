"""Verify frozen-model external-pilot outputs and closed deployment/tuning gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from validate_external_text_intake import sha256_file


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def resolve(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    args = parser.parse_args()
    registry = load_json(args.registry)
    root = args.registry.resolve().parents[2]
    errors: list[str] = []
    checked = []
    if registry.get("evaluation_id") != "ISI_TEXT_BASELINE_V2_EXTERNAL_PILOT_V1":
        errors.append("Unexpected evaluation ID")
    if registry.get("status") != "FROZEN_MODEL_EXTERNAL_DIAGNOSTIC_COMPLETE_NOT_FOR_DEPLOYMENT":
        errors.append("Unexpected status")
    entries = list(registry.get("implementation", [])) + list(registry.get("inputs", {}).values())
    outputs = {item.get("role"): item for item in registry.get("outputs", [])}
    entries.extend(outputs.values())
    for item in entries:
        path = resolve(root, item.get("path"))
        actual = sha256_file(path) if path.is_file() else None
        checked.append({"path": str(path), "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"Artifact missing or changed: {path}")
    if set(outputs) != {"results_json", "predictions_jsonl", "report_markdown"}:
        errors.append("Unexpected output roles")
    report_path = resolve(root, outputs.get("results_json", {}).get("path", ""))
    predictions_path = resolve(root, outputs.get("predictions_jsonl", {}).get("path", ""))
    if report_path.is_file() and predictions_path.is_file():
        report = load_json(report_path)
        predictions = [
            json.loads(line) for line in predictions_path.read_text(encoding="utf-8").splitlines() if line
        ]
        if report.get("evaluation_id") != registry.get("evaluation_id"):
            errors.append("Report and registry IDs differ")
        if len(predictions) != 21 or len({item.get("case_id") for item in predictions}) != 21:
            errors.append("Expected 21 unique predictions")
        confusion = report.get("metrics", {}).get("confusion_matrix", {})
        actual_confusion = {"tn": 0, "fp": 0, "fn": 0, "tp": 0}
        for item in predictions:
            truth = item.get("expected_source_label")
            predicted = item.get("predicted_source_label")
            key = { (0, 0): "tn", (0, 1): "fp", (1, 0): "fn", (1, 1): "tp" }.get((truth, predicted))
            if key is None:
                errors.append(f"Invalid prediction values: {item.get('case_id')}")
            else:
                actual_confusion[key] += 1
        if confusion != actual_confusion:
            errors.append("Prediction rows do not reproduce the confusion matrix")
        if actual_confusion != {"tn": 5, "fp": 6, "fn": 2, "tp": 8}:
            errors.append(f"Unexpected frozen confusion matrix: {actual_confusion}")
        safety = report.get("safety_contract", {})
        if (
            safety.get("model_fit_operations") != 0
            or safety.get("threshold_changes") != 0
            or safety.get("vectorizer_changes") != 0
            or safety.get("deployment_allowed") is not False
        ):
            errors.append("External evaluation safety contract is open")
        interpretation = report.get("interpretation", {})
        if (
            interpretation.get("pilot_supports_deployment_claim") is not False
            or interpretation.get("pilot_may_be_used_for_tuning") is not False
        ):
            errors.append("Pilot interpretation gate is open")
    else:
        errors.append("Results or predictions are unavailable")
    print(json.dumps({"valid": not errors, "errors": errors, "checked": checked}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

