"""Evaluate the frozen Text Baseline V2 on the reconciled 21-case external pilot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import balanced_accuracy_score, f1_score

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for value in (ROOT, SCRIPTS):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

from mendeley_text_baseline_v2_common import THRESHOLD, binary_metrics, sha256_file


EXPECTED_MODEL_ID = "ISI_TEXT_BASELINE_V2"
EXPECTED_MODEL_SHA256 = "c58444996e0ae67a9739c588e3d088f1f57eb1af7f9105e10a647303ce72fc71"
LABEL_MAP = {"LEGITIMATE": 0, "CONFIRMED": 1}


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def model_path_from_registry(path: Path) -> tuple[Path, dict[str, object]]:
    registry = load_json(path)
    if registry.get("model_id") != EXPECTED_MODEL_ID:
        raise ValueError("Unexpected model ID")
    if registry.get("status") != "FROZEN_INTERNAL_BASELINE_NOT_FOR_DEPLOYMENT":
        raise ValueError("Model is not the frozen V2 baseline")
    matches = [item for item in registry.get("artifacts", []) if item.get("role") == "model"]
    if len(matches) != 1:
        raise ValueError("Model registry has no unique model artifact")
    model_path = Path(str(matches[0].get("path", "")))
    actual = sha256_file(model_path) if model_path.is_file() else None
    if actual != EXPECTED_MODEL_SHA256 or actual != matches[0].get("sha256"):
        raise ValueError("Frozen model artifact is missing or changed")
    return model_path, registry


def validate_gate(intake_path: Path, validation_path: Path) -> tuple[dict, dict]:
    intake = load_json(intake_path)
    validation = load_json(validation_path)
    if validation.get("input_sha256") != sha256_file(intake_path):
        raise ValueError("Validation report does not bind the supplied intake")
    if validation.get("batch_id") != intake.get("batch_id"):
        raise ValueError("Validation report and intake batch IDs differ")
    if (
        intake.get("status") != "RECONCILED"
        or validation.get("reporting_allowed") is not True
        or validation.get("structural_error_count") != 0
        or validation.get("eligible_count") != 21
        or validation.get("eligible_confirmed") != 10
        or validation.get("eligible_legitimate") != 11
    ):
        raise ValueError("External reporting gate is not open for exactly 10+11 cases")
    records = intake.get("records", [])
    if len(records) != 21 or len({item.get("case_id") for item in records}) != 21:
        raise ValueError("Expected 21 unique external records")
    result_cases = {
        item.get("case_id") for item in validation.get("record_results", []) if item.get("eligible") is True
    }
    if result_cases != {item.get("case_id") for item in records}:
        raise ValueError("Validation eligibility does not cover every intake case")
    return intake, validation


def prepare_output_paths(output_dir: Path) -> dict[str, Path]:
    paths = {
        "report": output_dir / "external_pilot_results_v1.json",
        "predictions": output_dir / "external_pilot_predictions_v1.jsonl",
        "markdown": output_dir / "external_pilot_report_v1.md",
    }
    existing = [path for path in paths.values() if path.exists()]
    if existing:
        raise FileExistsError(f"Refusing to overwrite frozen output: {existing[0]}")
    output_dir.mkdir(parents=True, exist_ok=True)
    return paths


def bootstrap_intervals(
    truth: np.ndarray,
    predictions: np.ndarray,
    *,
    iterations: int = 5000,
    seed: int = 20260924,
) -> dict[str, object]:
    rng = np.random.default_rng(seed)
    values = {"accuracy": [], "balanced_accuracy": [], "macro_f1": []}
    for _ in range(iterations):
        indices = rng.integers(0, len(truth), len(truth))
        sampled_truth = truth[indices]
        if len(np.unique(sampled_truth)) < 2:
            continue
        sampled_predictions = predictions[indices]
        values["accuracy"].append(float(np.mean(sampled_truth == sampled_predictions)))
        values["balanced_accuracy"].append(
            float(balanced_accuracy_score(sampled_truth, sampled_predictions))
        )
        values["macro_f1"].append(
            float(f1_score(sampled_truth, sampled_predictions, labels=[0, 1], average="macro", zero_division=0))
        )
    return {
        "method": "nonparametric record-level bootstrap",
        "seed": seed,
        "requested_iterations": iterations,
        "valid_iterations": len(values["accuracy"]),
        "interval_level": 0.95,
        "intervals": {
            name: {
                "lower": round(float(np.quantile(scores, 0.025)), 6),
                "upper": round(float(np.quantile(scores, 0.975)), 6),
            }
            for name, scores in values.items()
        },
    }


def write_predictions(path: Path, records: list[dict], predictions, probabilities) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record, prediction, probability in zip(records, predictions, probabilities):
            truth = LABEL_MAP[record["ground_truth_status"]]
            output = {
                "case_id": record["case_id"],
                "case_or_campaign_group_id": record["case_or_campaign_group_id"],
                "near_duplicate_group_id": record["near_duplicate_group_id"],
                "ground_truth_status": record["ground_truth_status"],
                "expected_source_label": truth,
                "predicted_source_label": int(prediction),
                "score_label_1": round(float(probability), 10),
                "correct": bool(int(prediction) == truth),
                "artifact_text_sha256": record["artifact"]["text_sha256"],
                "score_semantics": "frozen Mendeley deceptive/suspicious source-label score; not real-world scam probability",
            }
            handle.write(json.dumps(output, ensure_ascii=False, sort_keys=True) + "\n")


def write_markdown(path: Path, report: dict[str, object]) -> None:
    metrics = report["metrics"]
    confusion = metrics["confusion_matrix"]
    errors = report["error_analysis"]
    lines = [
        "# Text Baseline V2 – external pilot V1",
        "",
        "Đây là diagnostic pilot trên 21 website snapshot đã reconciled. Kết quả không phải "
        "bằng chứng deployment và score label 1 không phải xác suất lừa đảo ngoài đời thực.",
        "",
        "## Metrics",
        "",
        f"- Accuracy: `{metrics['accuracy']}`",
        f"- Balanced accuracy: `{metrics['balanced_accuracy']}`",
        f"- Macro-F1: `{metrics['macro_f1']}`",
        f"- ROC-AUC: `{metrics['roc_auc']}`",
        f"- Confusion: TN={confusion['tn']}, FP={confusion['fp']}, FN={confusion['fn']}, TP={confusion['tp']}",
        "",
        "## Errors",
        "",
    ]
    if errors:
        for item in errors:
            lines.append(
                f"- `{item['case_id']}`: truth `{item['ground_truth_status']}`, "
                f"predicted `{item['predicted_source_label']}`, score `{item['score_label_1']}`"
            )
    else:
        lines.append("- Không có lỗi trong pilot này.")
    lines.extend(
        [
            "",
            "## Giới hạn",
            "",
            "- Chỉ 21 case, lấy từ hai nhánh thu thập có cấu trúc khác nhau; không đại diện phân phối thực tế.",
            "- Nhãn được AI review và project owner chấp nhận tiếp tục; chưa có independent second-reviewer rereview.",
            "- Model và threshold giữ nguyên; kết quả không được dùng để tune lại trên pilot này.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-registry", type=Path, required=True)
    parser.add_argument("--intake", type=Path, required=True)
    parser.add_argument("--validation-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-at", required=True)
    args = parser.parse_args()
    model_path, model_registry = model_path_from_registry(args.model_registry)
    intake, validation = validate_gate(args.intake, args.validation_report)
    paths = prepare_output_paths(args.output_dir)

    bundle = joblib.load(model_path)
    metadata = bundle.get("metadata", {})
    if (
        bundle.get("model_id") != EXPECTED_MODEL_ID
        or metadata.get("threshold") != THRESHOLD
        or metadata.get("feature_policy") != "text_content only"
        or metadata.get("fit_partitions") != ["train", "validation"]
        or metadata.get("excluded_partitions") != ["auxiliary", "quarantine"]
        or metadata.get("deployment_allowed") is not False
    ):
        raise ValueError("Frozen model bundle contract mismatch")

    records = sorted(intake["records"], key=lambda item: item["case_id"])
    text_values = [item["artifact"]["text"] for item in records]
    truth = np.asarray([LABEL_MAP[item["ground_truth_status"]] for item in records], dtype=np.int64)
    matrix = bundle["vectorizer"].transform(text_values).tocsr()
    probabilities = bundle["classifier"].predict_proba(matrix)[:, 1]
    predictions = (probabilities >= THRESHOLD).astype(np.int64)
    metrics = binary_metrics(truth, predictions, probabilities)
    write_predictions(paths["predictions"], records, predictions, probabilities)

    error_analysis = []
    for record, prediction, probability, expected in zip(records, predictions, probabilities, truth):
        if int(prediction) != int(expected):
            error_analysis.append(
                {
                    "case_id": record["case_id"],
                    "ground_truth_status": record["ground_truth_status"],
                    "expected_source_label": int(expected),
                    "predicted_source_label": int(prediction),
                    "score_label_1": round(float(probability), 10),
                }
            )
    report = {
        "evaluation_id": "ISI_TEXT_BASELINE_V2_EXTERNAL_PILOT_V1",
        "run_at": args.run_at,
        "status": "FROZEN_MODEL_EXTERNAL_DIAGNOSTIC_COMPLETE_NOT_FOR_DEPLOYMENT",
        "model": {
            "model_id": EXPECTED_MODEL_ID,
            "registry_path": str(args.model_registry),
            "registry_sha256": sha256_file(args.model_registry),
            "artifact_path": str(model_path),
            "artifact_sha256": sha256_file(model_path),
            "threshold": THRESHOLD,
            "fit_operations": 0,
            "configuration_changes": 0,
        },
        "data": {
            "intake_path": str(args.intake),
            "intake_sha256": sha256_file(args.intake),
            "validation_report_path": str(args.validation_report),
            "validation_report_sha256": sha256_file(args.validation_report),
            "record_count": len(records),
            "confirmed_count": int(np.sum(truth == 1)),
            "legitimate_count": int(np.sum(truth == 0)),
            "all_records_eligible": validation.get("eligible_count") == len(records),
            "independent_human_evidence_rereview": False,
        },
        "metrics": metrics,
        "bootstrap_uncertainty": bootstrap_intervals(truth, predictions),
        "prediction_profile": {
            "predicted_label_1_count": int(np.sum(predictions == 1)),
            "predicted_label_0_count": int(np.sum(predictions == 0)),
            "correct_count": int(np.sum(predictions == truth)),
            "error_count": int(np.sum(predictions != truth)),
        },
        "error_analysis": error_analysis,
        "interpretation": {
            "score_label_1_semantics": model_registry["label_semantics"],
            "real_world_scam_probability": False,
            "pilot_supports_deployment_claim": False,
            "pilot_may_be_used_for_tuning": False,
            "warning": "Small structured pilot; confidence intervals are wide and collection branch is confounded with class.",
        },
        "safety_contract": {
            "network_operations": 0,
            "model_fit_operations": 0,
            "threshold_changes": 0,
            "vectorizer_changes": 0,
            "source_text_modified": False,
            "warning_text_used_as_model_input": False,
            "deployment_allowed": False,
        },
        "artifacts": {
            "predictions": {
                "path": str(paths["predictions"]),
                "sha256": sha256_file(paths["predictions"]),
            }
        },
    }
    paths["report"].write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_markdown(paths["markdown"], report)
    print(
        json.dumps(
            {
                "report": str(paths["report"]),
                "report_sha256": sha256_file(paths["report"]),
                "predictions": str(paths["predictions"]),
                "predictions_sha256": sha256_file(paths["predictions"]),
                "markdown": str(paths["markdown"]),
                "markdown_sha256": sha256_file(paths["markdown"]),
                "metrics": metrics,
                "error_count": len(error_analysis),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

