"""Score the frozen Text Baseline V2 once on the accepted Wayback-language V2 benchmark."""

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
from mendeley_text_baseline_v2_common import THRESHOLD, binary_metrics, sha256_file


EVALUATION_ID = "ISI_TEXT_BASELINE_V2_WAYBACK_LANGUAGE_V2"
MODEL_ID = "ISI_TEXT_BASELINE_V2"
BENCHMARK_ID = "EXTERNAL_TEXT_WAYBACK_LANGUAGE_BENCHMARK_V2"
ACCEPTANCE_ID = "EXTERNAL_TEXT_WAYBACK_LANGUAGE_OWNER_ACCEPTANCE_V2"
LANGUAGE_STRATUM = "ENGLISH"
CAPTURE_STRATUM = "WAYBACK_ARCHIVED_HOMEPAGE_HTML"
EXPECTED_MODEL_SHA256 = "c58444996e0ae67a9739c588e3d088f1f57eb1af7f9105e10a647303ce72fc71"
EXPECTED_BENCHMARK_SHA256 = "4567acf6f27f275838283e3f335f859823af785109043e68cdf92d8fd14b2835"
LABEL_MAP = {"LEGITIMATE": 0, "CONFIRMED": 1}


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def validate_model_registry(path: Path) -> tuple[Path, dict[str, object]]:
    registry = load_json(path)
    if registry.get("model_id") != MODEL_ID:
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


def validate_scoring_gate(
    benchmark_path: Path,
    benchmark_registry_path: Path,
    acceptance_path: Path,
    model_registry_path: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    benchmark = load_json(benchmark_path)
    registry = load_json(benchmark_registry_path)
    acceptance = load_json(acceptance_path)
    benchmark_hash = sha256_file(benchmark_path)
    registry_hash = sha256_file(benchmark_registry_path)
    model_registry_hash = sha256_file(model_registry_path)
    if benchmark_hash != EXPECTED_BENCHMARK_SHA256:
        raise ValueError("Wayback-language benchmark is missing or changed")
    if benchmark.get("benchmark_id") != BENCHMARK_ID:
        raise ValueError("Unexpected benchmark ID")
    if benchmark.get("status") != "OWNER_ACCEPTANCE_REQUIRED_BEFORE_MODEL_SCORING":
        raise ValueError("Unexpected frozen benchmark status")
    if benchmark.get("training_eligible") is not False:
        raise ValueError("Benchmark incorrectly allows training")
    if registry.get("registry_id") != BENCHMARK_ID:
        raise ValueError("Benchmark registry ID mismatch")
    if registry.get("status") != "FROZEN_OWNER_ACCEPTANCE_REQUIRED_BEFORE_MODEL_SCORING":
        raise ValueError("Unexpected benchmark registry status")
    benchmark_entries = [item for item in registry.get("artifacts", []) if item.get("role") == "benchmark"]
    if len(benchmark_entries) != 1 or benchmark_entries[0].get("sha256") != benchmark_hash:
        raise ValueError("Benchmark registry does not bind the supplied benchmark")
    if acceptance.get("acceptance_id") != ACCEPTANCE_ID:
        raise ValueError("Unexpected owner acceptance ID")
    if acceptance.get("accepted_for_frozen_model_scoring") is not True:
        raise ValueError("Owner acceptance does not open frozen scoring")
    if acceptance.get("accepted_for_training_or_tuning") is not False:
        raise ValueError("Acceptance incorrectly permits training or tuning")
    if acceptance.get("diagnostic_evaluation_only") is not True:
        raise ValueError("Acceptance is not limited to diagnostic evaluation")
    if acceptance.get("independent_human_review_claimed") is not False:
        raise ValueError("Acceptance incorrectly claims human second review")
    scope = acceptance.get("scope", {})
    if (
        scope.get("benchmark_id") != BENCHMARK_ID
        or scope.get("benchmark_sha256") != benchmark_hash
        or scope.get("benchmark_registry_sha256") != registry_hash
        or scope.get("record_count") != 38
        or scope.get("confirmed_count") != 19
        or scope.get("legitimate_count") != 19
        or scope.get("language_stratum") != LANGUAGE_STRATUM
        or scope.get("capture_stratum") != CAPTURE_STRATUM
    ):
        raise ValueError("Owner acceptance scope does not bind the frozen benchmark")
    scoring = acceptance.get("scoring_contract", {})
    if (
        scoring.get("model_id") != MODEL_ID
        or scoring.get("model_registry_sha256") != model_registry_hash
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
    if len(records) != 38 or len({item.get("benchmark_record_id") for item in records}) != 38:
        raise ValueError("Expected 38 unique benchmark records")
    counts = {label: sum(item.get("ground_truth_status") == label for item in records) for label in LABEL_MAP}
    if counts != {"LEGITIMATE": 19, "CONFIRMED": 19}:
        raise ValueError(f"Unexpected benchmark class counts: {counts}")
    for item in records:
        artifact = item.get("artifact", {})
        provenance = item.get("review_provenance", {})
        status = item.get("ground_truth_status")
        if (
            item.get("language_stratum") != LANGUAGE_STRATUM
            or item.get("capture_stratum") != CAPTURE_STRATUM
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
    return benchmark, acceptance


def prepare_output_paths(output_dir: Path) -> dict[str, Path]:
    paths = {
        "report": output_dir / "wayback_language_results_v2.json",
        "predictions": output_dir / "wayback_language_predictions_v2.jsonl",
        "markdown": output_dir / "wayback_language_report_v2.md",
    }
    existing = [path for path in paths.values() if path.exists()]
    if existing:
        raise FileExistsError(f"Refusing to overwrite frozen output: {existing[0]}")
    output_dir.mkdir(parents=True, exist_ok=True)
    return paths


def write_predictions(path: Path, records: list[dict], predictions, probabilities) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record, prediction, probability in zip(records, predictions, probabilities):
            truth = LABEL_MAP[record["ground_truth_status"]]
            row = {
                "benchmark_record_id": record["benchmark_record_id"],
                "language_stratum": record["language_stratum"],
                "capture_stratum": record["capture_stratum"],
                "ground_truth_status": record["ground_truth_status"],
                "expected_source_label": truth,
                "predicted_source_label": int(prediction),
                "score_label_1": round(float(probability), 10),
                "correct": bool(int(prediction) == truth),
                "artifact_text_sha256": record["artifact"]["text_sha256"],
                "score_semantics": "frozen Mendeley deceptive/suspicious source-label score; not real-world scam probability",
            }
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_markdown(path: Path, report: dict[str, object]) -> None:
    metrics = report["metrics"]
    confusion = metrics["confusion_matrix"]
    lines = [
        "# Text Baseline V2 – Wayback language benchmark V2",
        "",
        "Mô hình frozen được chấm đúng một lần trên 38 English archived-homepage artifacts cân bằng. Đây là diagnostic external evaluation, không phải phê duyệt deployment.",
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
        "- Cả hai lớp cùng dùng `WAYBACK_ARCHIVED_HOMEPAGE_HTML` và cùng English stratum.",
        "- Primary và second review đều là AI review; second review độc lập và làm mù, không phải human review.",
        "- Model chỉ nhận visible text; warning/registration evidence, provenance và review rationale không vào feature matrix.",
        "- Không fit lại model, không đổi threshold/vectorizer và không dùng benchmark này để tuning.",
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
    benchmark, acceptance = validate_scoring_gate(
        args.benchmark, args.benchmark_registry, args.owner_acceptance, args.model_registry
    )
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
        "status": "FROZEN_MODEL_WAYBACK_LANGUAGE_V2_DIAGNOSTIC_COMPLETE_NOT_FOR_DEPLOYMENT",
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
            "language_stratum": LANGUAGE_STRATUM,
            "capture_stratum": CAPTURE_STRATUM,
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
