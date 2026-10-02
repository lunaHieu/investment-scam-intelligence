"""Score the frozen Text Baseline V2 once on the owner-accepted Wayback holdout V3."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for value in (ROOT, SCRIPTS):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

from evaluate_text_baseline_v2_external_pilot import bootstrap_intervals
from evaluate_text_baseline_v2_wayback_language_v2 import validate_model_registry, write_predictions
from mendeley_text_baseline_v2_common import THRESHOLD, binary_metrics, sha256_file


EVALUATION_ID = "ISI_TEXT_BASELINE_V2_WAYBACK_HOLDOUT_V3"
MODEL_ID = "ISI_TEXT_BASELINE_V2"
BENCHMARK_ID = "EXTERNAL_TEXT_WAYBACK_HOLDOUT_BENCHMARK_V3"
ACCEPTANCE_ID = "EXTERNAL_TEXT_WAYBACK_HOLDOUT_OWNER_ACCEPTANCE_V3"
EXPECTED_BENCHMARK_SHA256 = "f234027f21f228fff39ea833a085eb46b9dddabb23004c1a2ad9751122c2df75"
EXPECTED_MODEL_SHA256 = "c58444996e0ae67a9739c588e3d088f1f57eb1af7f9105e10a647303ce72fc71"
LABEL_MAP = {"LEGITIMATE": 0, "CONFIRMED": 1}


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def validate_scoring_gate(
    benchmark_path: Path,
    benchmark_registry_path: Path,
    acceptance_path: Path,
    model_registry_path: Path,
) -> dict[str, object]:
    benchmark = load_json(benchmark_path)
    registry = load_json(benchmark_registry_path)
    acceptance = load_json(acceptance_path)
    benchmark_hash = sha256_file(benchmark_path)
    registry_hash = sha256_file(benchmark_registry_path)
    model_registry_hash = sha256_file(model_registry_path)
    if benchmark_hash != EXPECTED_BENCHMARK_SHA256:
        raise ValueError("Wayback holdout V3 is missing or changed")
    if benchmark.get("benchmark_id") != BENCHMARK_ID or benchmark.get("status") != "OWNER_ACCEPTANCE_REQUIRED_BEFORE_MODEL_SCORING":
        raise ValueError("Unexpected frozen benchmark identity or status")
    if benchmark.get("training_eligible") is not False:
        raise ValueError("Benchmark incorrectly allows training")
    if registry.get("registry_id") != BENCHMARK_ID or registry.get("status") != "FROZEN_OWNER_ACCEPTANCE_REQUIRED_BEFORE_MODEL_SCORING":
        raise ValueError("Unexpected benchmark registry identity or status")
    benchmark_entries = [item for item in registry.get("artifacts", []) if item.get("role") == "benchmark"]
    if len(benchmark_entries) != 1 or benchmark_entries[0].get("sha256") != benchmark_hash:
        raise ValueError("Benchmark registry does not bind the supplied benchmark")
    if acceptance.get("acceptance_id") != ACCEPTANCE_ID:
        raise ValueError("Unexpected owner acceptance ID")
    if acceptance.get("accepted_for_frozen_model_scoring") is not True or acceptance.get("accepted_for_training_or_tuning") is not False:
        raise ValueError("Owner acceptance scoring/training scope mismatch")
    if acceptance.get("diagnostic_evaluation_only") is not True or acceptance.get("independent_human_review_claimed") is not False:
        raise ValueError("Owner acceptance is not restricted to non-human-reviewed diagnostic evaluation")
    scope = acceptance.get("scope", {})
    if (
        scope.get("benchmark_id") != BENCHMARK_ID
        or scope.get("benchmark_sha256") != benchmark_hash
        or scope.get("benchmark_registry_sha256") != registry_hash
        or scope.get("record_count") != 30
        or scope.get("confirmed_count") != 15
        or scope.get("legitimate_count") != 15
        or scope.get("language_stratum") != "ENGLISH"
        or scope.get("capture_stratum") != "WAYBACK_ARCHIVED_HOMEPAGE_HTML"
    ):
        raise ValueError("Owner acceptance does not bind the frozen V3 holdout")
    scoring = acceptance.get("scoring_contract", {})
    if (
        scoring.get("model_id") != MODEL_ID
        or scoring.get("model_registry_sha256") != model_registry_hash
        or scoring.get("model_artifact_sha256") != EXPECTED_MODEL_SHA256
        or scoring.get("allowed_model_input") != "benchmark.records[].artifact.visible_text only"
        or scoring.get("warning_or_registry_evidence_as_model_input_allowed") is not False
        or scoring.get("review_rationale_as_model_input_allowed") is not False
        or scoring.get("model_configuration_changes_allowed") is not False
        or scoring.get("threshold_changes_allowed") is not False
        or scoring.get("vectorizer_changes_allowed") is not False
        or scoring.get("model_fit_allowed") is not False
        or scoring.get("use_benchmark_for_tuning") is not False
        or scoring.get("deployment_allowed") is not False
    ):
        raise ValueError("Owner acceptance scoring contract is open or mismatched")
    records = benchmark.get("records", [])
    if len(records) != 30 or len({item.get("benchmark_record_id") for item in records}) != 30:
        raise ValueError("Expected 30 unique benchmark records")
    counts = {label: sum(item.get("ground_truth_status") == label for item in records) for label in LABEL_MAP}
    if counts != {"LEGITIMATE": 15, "CONFIRMED": 15}:
        raise ValueError(f"Unexpected benchmark class counts: {counts}")
    for item in records:
        artifact = item.get("artifact", {})
        provenance = item.get("review_provenance", {})
        status = item.get("ground_truth_status")
        if (
            item.get("language_stratum") != "ENGLISH"
            or item.get("capture_stratum") != "WAYBACK_ARCHIVED_HOMEPAGE_HTML"
            or item.get("label_confidence") != "HIGH"
            or item.get("training_eligible") is not False
            or provenance.get("independent_ai_second_review") is not True
            or provenance.get("independent_human_second_review") is not False
            or provenance.get("primary_decision") != status
            or provenance.get("primary_confidence") != "HIGH"
            or provenance.get("second_decision") != status
            or provenance.get("second_confidence") != "HIGH"
        ):
            raise ValueError(f"Benchmark review contract mismatch: {item.get('benchmark_record_id')}")
        text = str(artifact.get("visible_text", ""))
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != artifact.get("text_sha256"):
            raise ValueError(f"Benchmark text hash mismatch: {item.get('benchmark_record_id')}")
    return benchmark


def prepare_output_paths(output_dir: Path) -> dict[str, Path]:
    paths = {
        "report": output_dir / "wayback_holdout_results_v3.json",
        "predictions": output_dir / "wayback_holdout_predictions_v3.jsonl",
        "markdown": output_dir / "wayback_holdout_report_v3.md",
    }
    existing = [path for path in paths.values() if path.exists()]
    if existing:
        raise FileExistsError(f"Refusing to overwrite frozen output: {existing[0]}")
    output_dir.mkdir(parents=True, exist_ok=True)
    return paths


def write_markdown(path: Path, report: dict[str, object]) -> None:
    metrics = report["metrics"]
    confusion = metrics["confusion_matrix"]
    lines = [
        "# Text Baseline V2 – Wayback holdout V3",
        "",
        "Mô hình frozen được chấm đúng một lần trên 30 English archived-homepage artifacts cân bằng. Đây là diagnostic external evaluation, không phải phê duyệt deployment.",
        "",
        "## Kết quả",
        "",
        f"- Accuracy: `{metrics['accuracy']}`",
        f"- Balanced accuracy: `{metrics['balanced_accuracy']}`",
        f"- Macro-F1: `{metrics['macro_f1']}`",
        f"- ROC-AUC: `{metrics['roc_auc']}`",
        f"- Average precision: `{metrics['average_precision']}`",
        f"- Confusion: TN={confusion['tn']}, FP={confusion['fp']}, FN={confusion['fn']}, TP={confusion['tp']}",
        "",
        "## Giới hạn bắt buộc",
        "",
        "- Hai lớp dùng cùng English và Wayback archived-homepage stratum.",
        "- Primary và second review là AI review; second review độc lập và làm mù, không phải human review.",
        "- Model chỉ nhận visible text; evidence, provenance, rationale và label không vào feature matrix.",
        "- Không fit lại model, đổi threshold/vectorizer hoặc dùng holdout để tuning.",
        "- Score label 1 không phải xác suất lừa đảo ngoài thực tế.",
        "- Kết quả không hỗ trợ deployment, enforcement, blocking hoặc tư vấn tài chính.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-registry", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--benchmark-registry", type=Path, required=True)
    parser.add_argument("--owner-acceptance", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-at", required=True)
    args = parser.parse_args()
    model_path, model_registry = validate_model_registry(args.model_registry)
    if sha256_file(model_path) != EXPECTED_MODEL_SHA256:
        raise ValueError("Unexpected frozen model artifact")
    benchmark = validate_scoring_gate(args.benchmark, args.benchmark_registry, args.owner_acceptance, args.model_registry)
    paths = prepare_output_paths(args.output_dir)
    bundle = joblib.load(model_path)
    metadata = bundle.get("metadata", {})
    if (
        bundle.get("model_id") != MODEL_ID
        or metadata.get("threshold") != THRESHOLD
        or metadata.get("feature_policy") != "text_content only"
        or metadata.get("fit_partitions") != ["train", "validation"]
        or metadata.get("excluded_partitions") != ["auxiliary", "quarantine"]
        or metadata.get("deployment_allowed") is not False
    ):
        raise ValueError("Frozen model bundle contract mismatch")
    records = sorted(benchmark["records"], key=lambda item: item["benchmark_record_id"])
    texts = [item["artifact"]["visible_text"] for item in records]
    truth = np.asarray([LABEL_MAP[item["ground_truth_status"]] for item in records], dtype=np.int64)
    matrix = bundle["vectorizer"].transform(texts).tocsr()
    probabilities = bundle["classifier"].predict_proba(matrix)[:, 1]
    predictions = (probabilities >= THRESHOLD).astype(np.int64)
    metrics = binary_metrics(truth, predictions, probabilities)
    write_predictions(paths["predictions"], records, predictions, probabilities)
    errors = [
        {
            "benchmark_record_id": record["benchmark_record_id"],
            "ground_truth_status": record["ground_truth_status"],
            "expected_source_label": int(expected),
            "predicted_source_label": int(prediction),
            "score_label_1": round(float(probability), 10),
        }
        for record, expected, prediction, probability in zip(records, truth, predictions, probabilities)
        if int(expected) != int(prediction)
    ]
    report = {
        "evaluation_id": EVALUATION_ID,
        "run_at": args.run_at,
        "status": "FROZEN_MODEL_WAYBACK_HOLDOUT_V3_DIAGNOSTIC_COMPLETE_NOT_FOR_DEPLOYMENT",
        "model": {
            "model_id": MODEL_ID,
            "registry_path": str(args.model_registry),
            "registry_sha256": sha256_file(args.model_registry),
            "artifact_path": str(model_path),
            "artifact_sha256": sha256_file(model_path),
            "threshold": THRESHOLD,
            "fit_operations": 0,
            "configuration_changes": 0,
        },
        "data": {
            "benchmark_id": BENCHMARK_ID,
            "benchmark_path": str(args.benchmark),
            "benchmark_sha256": sha256_file(args.benchmark),
            "benchmark_registry_path": str(args.benchmark_registry),
            "benchmark_registry_sha256": sha256_file(args.benchmark_registry),
            "owner_acceptance_path": str(args.owner_acceptance),
            "owner_acceptance_sha256": sha256_file(args.owner_acceptance),
            "record_count": len(records),
            "confirmed_count": int(np.sum(truth == 1)),
            "legitimate_count": int(np.sum(truth == 0)),
            "language_stratum": "ENGLISH",
            "capture_stratum": "WAYBACK_ARCHIVED_HOMEPAGE_HTML",
            "independent_ai_second_review": True,
            "independent_human_second_review": False,
        },
        "metrics": metrics,
        "bootstrap_uncertainty": bootstrap_intervals(truth, predictions, seed=20261002),
        "prediction_profile": {
            "predicted_label_1_count": int(np.sum(predictions == 1)),
            "predicted_label_0_count": int(np.sum(predictions == 0)),
            "correct_count": int(np.sum(predictions == truth)),
            "error_count": int(np.sum(predictions != truth)),
        },
        "errors": errors,
        "interpretation": {
            "score_label_1_semantics": model_registry["label_semantics"],
            "real_world_scam_probability": False,
            "same_language_and_capture_stratum_reduce_but_do_not_eliminate_source_confounding": True,
            "benchmark_may_be_used_for_tuning": False,
            "evaluation_supports_deployment_claim": False,
        },
        "safety_contract": {
            "network_operations": 0,
            "model_fit_operations": 0,
            "threshold_changes": 0,
            "vectorizer_changes": 0,
            "warning_or_registry_evidence_used_as_model_input": False,
            "review_rationale_used_as_model_input": False,
            "source_text_modified": False,
            "training_allowed": False,
            "deployment_allowed": False,
        },
        "artifacts": {
            "predictions": {"path": str(paths["predictions"]), "sha256": sha256_file(paths["predictions"])}
        },
    }
    paths["report"].write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(paths["markdown"], report)
    print(json.dumps({
        "report": str(paths["report"]),
        "report_sha256": sha256_file(paths["report"]),
        "predictions": str(paths["predictions"]),
        "predictions_sha256": sha256_file(paths["predictions"]),
        "markdown": str(paths["markdown"]),
        "markdown_sha256": sha256_file(paths["markdown"]),
        "metrics": metrics,
        "error_count": len(errors),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
