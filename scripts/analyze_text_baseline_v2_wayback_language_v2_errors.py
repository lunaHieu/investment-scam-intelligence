"""Diagnose Wayback-language V2 errors without fitting, tuning, or relabeling."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for value in (ROOT, SCRIPTS):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

from analyze_mendeley_text_baseline_v2_errors import (
    calibration_summary,
    nearest_fit_neighbors,
    numeric_summary,
    redact_excerpt,
    top_row_contributions,
    vocabulary_coverage,
)
from mendeley_text_baseline_v2_common import (
    EXPECTED_SPLIT_SHA256,
    THRESHOLD,
    read_selection_data,
    sha256_file,
    texts,
)


ANALYSIS_ID = "ISI_TEXT_BASELINE_V2_WAYBACK_LANGUAGE_V2_ERROR_ANALYSIS"
EVALUATION_ID = "ISI_TEXT_BASELINE_V2_WAYBACK_LANGUAGE_V2"
EXPECTED_MODEL_SHA256 = "c58444996e0ae67a9739c588e3d088f1f57eb1af7f9105e10a647303ce72fc71"
LABEL_MAP = {"LEGITIMATE": 0, "CONFIRMED": 1}


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict[str, object]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line:
            raise ValueError(f"Blank JSONL line: {line_number}")
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"JSONL line is not an object: {line_number}")
        rows.append(value)
    return rows


def resolve(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def frozen_inputs(evaluation_registry_path: Path) -> dict[str, Path]:
    registry = load_json(evaluation_registry_path)
    if registry.get("analysis_id") != EVALUATION_ID:
        raise ValueError("Unexpected Wayback-language V2 evaluation registry")
    if registry.get("status") != "FROZEN_MODEL_WAYBACK_LANGUAGE_V2_DIAGNOSTIC_COMPLETE_NOT_FOR_DEPLOYMENT":
        raise ValueError("Wayback-language V2 evaluation is not frozen")
    root = evaluation_registry_path.resolve().parents[2]
    roles = {
        **{item["role"]: item for item in registry.get("inputs", [])},
        **{item["role"]: item for item in registry.get("outputs", [])},
    }
    required = {"model_registry", "benchmark", "owner_acceptance", "results_json", "predictions_jsonl"}
    if not required.issubset(roles):
        raise ValueError("Evaluation registry is missing required frozen inputs")
    paths: dict[str, Path] = {}
    for role in required:
        item = roles[role]
        path = resolve(root, item.get("path", ""))
        actual = sha256_file(path) if path.is_file() else None
        if actual != item.get("sha256"):
            raise ValueError(f"Frozen input missing or changed: {role}")
        paths[role] = path
    model_registry = load_json(paths["model_registry"])
    model_items = {item["role"]: item for item in model_registry.get("artifacts", [])}
    for role in ("model", "group_split_dataset"):
        item = model_items.get(role, {})
        path = Path(str(item.get("path", "")))
        actual = sha256_file(path) if path.is_file() else None
        if actual != item.get("sha256"):
            raise ValueError(f"Frozen model input missing or changed: {role}")
        paths[role] = path
    if sha256_file(paths["model"]) != EXPECTED_MODEL_SHA256:
        raise ValueError("Unexpected frozen model hash")
    if sha256_file(paths["group_split_dataset"]) != EXPECTED_SPLIT_SHA256:
        raise ValueError("Unexpected frozen split hash")
    return paths


def prepare_output_paths(output_dir: Path) -> dict[str, Path]:
    paths = {
        "report": output_dir / "wayback_language_error_analysis_v2.json",
        "diagnostics": output_dir / "wayback_language_diagnostics_v2.jsonl",
        "errors": output_dir / "wayback_language_error_queue_v2.jsonl",
        "near_threshold": output_dir / "wayback_language_near_threshold_queue_v2.jsonl",
        "markdown": output_dir / "wayback_language_error_analysis_v2.md",
    }
    existing = [path for path in paths.values() if path.exists()]
    if existing:
        raise FileExistsError(f"Refusing to overwrite frozen output: {existing[0]}")
    output_dir.mkdir(parents=True, exist_ok=True)
    return paths


def feature_driver_summary(items: list[dict], direction: str, limit: int = 20) -> list[dict]:
    if direction not in {"toward_label_0", "toward_label_1"}:
        raise ValueError("Unsupported contribution direction")
    count: Counter[str] = Counter()
    total: defaultdict[str, float] = defaultdict(float)
    for item in items:
        for feature in item["feature_contributions"][direction]:
            name = feature["feature"]
            count[name] += 1
            total[name] += float(feature["logit_contribution"])
    ordered = sorted(count, key=lambda name: (-count[name], -abs(total[name]), name))[:limit]
    return [
        {
            "feature": name,
            "top_contribution_row_count": count[name],
            "summed_logit_contribution": round(total[name], 8),
        }
        for name in ordered
    ]


def matched_strata_summary(records: list[dict]) -> dict[str, object]:
    capture = Counter(item.get("capture_stratum") for item in records)
    language = Counter(item.get("language_stratum") for item in records)
    capture_by_label: dict[str, Counter] = defaultdict(Counter)
    language_by_label: dict[str, Counter] = defaultdict(Counter)
    reference_roles: dict[str, Counter] = defaultdict(Counter)
    for item in records:
        label = item["ground_truth_status"]
        capture_by_label[label][item.get("capture_stratum")] += 1
        language_by_label[label][item.get("language_stratum")] += 1
        role = item.get("evidence", {}).get("official_reference_record", {}).get("reference_role")
        reference_roles[label][role] += 1
    both_matched = (
        len(capture) == 1
        and len(language) == 1
        and set(capture_by_label) == {"CONFIRMED", "LEGITIMATE"}
        and set(language_by_label) == {"CONFIRMED", "LEGITIMATE"}
    )
    return {
        "capture_strata": dict(sorted(capture.items())),
        "language_strata": dict(sorted(language.items())),
        "capture_strata_by_label": {label: dict(sorted(values.items())) for label, values in sorted(capture_by_label.items())},
        "language_strata_by_label": {label: dict(sorted(values.items())) for label, values in sorted(language_by_label.items())},
        "both_labels_share_capture_and_language_strata": both_matched,
        "official_reference_roles_by_label_not_model_input": {
            label: {str(key): value for key, value in sorted(values.items(), key=lambda pair: str(pair[0]))}
            for label, values in sorted(reference_roles.items())
        },
        "implication": "Capture and language confounding are reduced, but official-reference provenance and case selection still differ by class.",
    }


def subset_summary(items: list[dict]) -> dict[str, object]:
    return {
        "row_count": len(items),
        "score_label_1": numeric_summary([float(item["score_label_1"]) for item in items]),
        "surface_token_count": numeric_summary([float(item["surface_token_count"]) for item in items]),
        "unique_vectorizer_term_coverage": numeric_summary([float(item["unique_vectorizer_term_coverage"]) for item in items]),
        "nearest_fit_cosine_similarity": numeric_summary([float(item["nearest_fit_cosine_similarity"]) for item in items]),
        "nonzero_feature_count": numeric_summary([float(item["nonzero_feature_count"]) for item in items]),
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_markdown(path: Path, report: dict[str, object]) -> None:
    counts = report["counts"]
    lines = [
        "# Text Baseline V2 – Wayback language V2 error analysis",
        "",
        "Phân tích này chỉ giải thích hành vi model đóng băng. Không fit, đổi threshold, relabel hoặc chọn model từ benchmark đã mở.",
        "",
        "## Tóm tắt",
        "",
        f"- Lỗi: {counts['error_count']}/38 ({counts['false_positive_count']} FP, {counts['false_negative_count']} FN).",
        f"- Dự đoán label 1: {counts['predicted_label_1_count']}/38.",
        f"- Lỗi cách threshold không quá 0,10: {counts['errors_within_0_10_of_threshold']}/{counts['error_count']}.",
        f"- Tổng case gần threshold (đúng hoặc sai): {counts['records_within_0_10_of_threshold']}/38.",
        "- Hai lớp cùng English và archived-homepage Wayback; nguồn evidence vẫn khác và không đi vào model.",
        "",
        "## Các case sai",
        "",
        "| Record | Host | Truth | Prediction | Score label 1 | Nearest Mendeley source | Similarity |",
        "|---|---|---|---:|---:|---|---:|",
    ]
    for item in report["errors"]:
        lines.append(
            f"| `{item['benchmark_record_id']}` | `{item['candidate_host']}` | `{item['ground_truth_status']}` | "
            f"`{item['predicted_source_label']}` | `{item['score_label_1']}` | "
            f"`{item['nearest_fit_source_dataset']}` | `{item['nearest_fit_cosine_similarity']}` |"
        )
    lines.extend([
        "",
        "## Diễn giải an toàn",
        "",
        "- Feature contributions mô tả logit của frozen TF-IDF model, không phải bằng chứng gian lận hoặc quan hệ nhân quả.",
        "- Nearest neighbors chỉ dùng train+validation đã fit trước đây để đo domain shift; internal test không được transform hoặc dùng.",
        "- Không được chọn feature, threshold hoặc cấu hình mới từ 38 case này rồi báo cáo lại cùng benchmark như đánh giá độc lập.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluation-registry", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-at", required=True)
    args = parser.parse_args()
    paths = frozen_inputs(args.evaluation_registry)
    outputs = prepare_output_paths(args.output_dir)
    benchmark = load_json(paths["benchmark"])
    evaluation_results = load_json(paths["results_json"])
    stored_predictions = load_jsonl(paths["predictions_jsonl"])
    records = sorted(benchmark["records"], key=lambda item: item["benchmark_record_id"])
    if [item["benchmark_record_id"] for item in records] != [item["benchmark_record_id"] for item in stored_predictions]:
        raise ValueError("Stored predictions and sorted benchmark do not align")
    bundle = joblib.load(paths["model"])
    vectorizer = bundle["vectorizer"]
    classifier = bundle["classifier"]
    external_matrix = vectorizer.transform([item["artifact"]["visible_text"] for item in records]).tocsr()
    probabilities = classifier.predict_proba(external_matrix)[:, 1]
    predictions = (probabilities >= THRESHOLD).astype(np.int64)
    truth = np.asarray([LABEL_MAP[item["ground_truth_status"]] for item in records], dtype=np.int64)
    for index, stored in enumerate(stored_predictions):
        if (
            int(stored["expected_source_label"]) != int(truth[index])
            or int(stored["predicted_source_label"]) != int(predictions[index])
            or not math.isclose(float(stored["score_label_1"]), float(probabilities[index]), rel_tol=0.0, abs_tol=5.1e-11)
        ):
            raise ValueError(f"Stored prediction mismatch: {stored.get('benchmark_record_id')}")
    splits, access = read_selection_data(paths["group_split_dataset"])
    fit_rows = splits["train"] + splits["validation"]
    fit_matrix = vectorizer.transform(texts(fit_rows)).tocsr()
    nearest_similarity, nearest_indices = nearest_fit_neighbors(external_matrix, fit_matrix)
    analyzer = vectorizer.build_analyzer()
    vocabulary = vectorizer.vocabulary_
    feature_names = vectorizer.get_feature_names_out()
    coefficients = classifier.coef_[0]
    intercept = float(classifier.intercept_[0])
    diagnostics = []
    for index, record in enumerate(records):
        row = external_matrix.getrow(index)
        text = record["artifact"]["visible_text"]
        term_count, matched_count, coverage = vocabulary_coverage(analyzer, vocabulary, text)
        nearest_index = int(nearest_indices[index])
        nearest = fit_rows[nearest_index] if nearest_index >= 0 else None
        contribution_sum = float(np.dot(row.data, coefficients[row.indices]))
        logit = intercept + contribution_sum
        reconstructed = 1.0 / (1.0 + math.exp(-logit))
        if not math.isclose(reconstructed, float(probabilities[index]), rel_tol=0.0, abs_tol=1e-10):
            raise ValueError(f"Contribution reconstruction failed: {record['benchmark_record_id']}")
        expected = int(truth[index])
        predicted = int(predictions[index])
        diagnostics.append({
            "benchmark_record_id": record["benchmark_record_id"],
            "candidate_host": record["artifact"]["candidate_host"],
            "ground_truth_status": record["ground_truth_status"],
            "expected_source_label": expected,
            "predicted_source_label": predicted,
            "correct": predicted == expected,
            "error_type": None if predicted == expected else "false_positive" if expected == 0 else "false_negative",
            "score_label_1": round(float(probabilities[index]), 10),
            "distance_from_threshold": round(abs(float(probabilities[index]) - THRESHOLD), 10),
            "near_threshold_within_0_10": abs(float(probabilities[index]) - THRESHOLD) <= 0.10,
            "language_stratum": record["language_stratum"],
            "capture_stratum": record["capture_stratum"],
            "surface_token_count": len(text.split()),
            "unique_analyzed_term_count": term_count,
            "matched_vocabulary_term_count": matched_count,
            "unique_vectorizer_term_coverage": round(float(coverage), 6),
            "nonzero_feature_count": int(row.nnz),
            "nearest_fit_record_id": nearest["record_id"] if nearest else None,
            "nearest_fit_source_dataset": nearest["source_dataset"] if nearest else None,
            "nearest_fit_partition": nearest["partition"] if nearest else None,
            "nearest_fit_source_label": int(nearest["label"]) if nearest else None,
            "nearest_fit_cosine_similarity": round(float(nearest_similarity[index]), 6),
            "model_intercept": round(intercept, 8),
            "feature_contribution_sum": round(contribution_sum, 8),
            "feature_contributions": top_row_contributions(row.indices, row.data, coefficients, feature_names, limit=10),
            "redacted_text_excerpt": redact_excerpt(text, limit=320),
        })
    errors = [item for item in diagnostics if not item["correct"]]
    near_threshold = [item for item in diagnostics if item["near_threshold_within_0_10"]]
    false_positives = [item for item in errors if item["error_type"] == "false_positive"]
    false_negatives = [item for item in errors if item["error_type"] == "false_negative"]
    true_positives = [item for item in diagnostics if item["correct"] and item["expected_source_label"] == 1]
    true_negatives = [item for item in diagnostics if item["correct"] and item["expected_source_label"] == 0]
    nearest_sources = Counter(item["nearest_fit_source_dataset"] for item in diagnostics)
    nearest_error_sources = Counter(item["nearest_fit_source_dataset"] for item in errors)
    strata_summary = matched_strata_summary(records)
    report = {
        "analysis_id": ANALYSIS_ID,
        "run_at": args.run_at,
        "status": "FROZEN_WAYBACK_LANGUAGE_V2_DIAGNOSTIC_COMPLETE_NO_TUNING",
        "inputs": {role: {"path": str(path), "sha256": sha256_file(path)} for role, path in sorted(paths.items())},
        "counts": {
            "record_count": len(diagnostics),
            "correct_count": len(diagnostics) - len(errors),
            "error_count": len(errors),
            "false_positive_count": len(false_positives),
            "false_negative_count": len(false_negatives),
            "predicted_label_1_count": int(np.sum(predictions == 1)),
            "predicted_label_0_count": int(np.sum(predictions == 0)),
            "errors_within_0_10_of_threshold": sum(item["near_threshold_within_0_10"] for item in errors),
            "records_within_0_10_of_threshold": len(near_threshold),
            "correct_records_within_0_10_of_threshold": sum(item["correct"] for item in near_threshold),
        },
        "frozen_external_metrics": evaluation_results["metrics"],
        "calibration": calibration_summary(truth, probabilities),
        "matched_strata_analysis": strata_summary,
        "subsets": {
            "true_positive": subset_summary(true_positives),
            "true_negative": subset_summary(true_negatives),
            "false_positive": subset_summary(false_positives),
            "false_negative": subset_summary(false_negatives),
            "near_threshold": subset_summary(near_threshold),
        },
        "nearest_fit_source_profile": {
            "all_records": dict(sorted(nearest_sources.items())),
            "errors": dict(sorted(nearest_error_sources.items())),
        },
        "error_feature_drivers": {
            "false_positive_toward_label_1": feature_driver_summary(false_positives, "toward_label_1"),
            "false_positive_counterevidence_toward_label_0": feature_driver_summary(false_positives, "toward_label_0"),
            "false_negative_toward_label_0": feature_driver_summary(false_negatives, "toward_label_0"),
            "false_negative_counterevidence_toward_label_1": feature_driver_summary(false_negatives, "toward_label_1"),
        },
        "errors": errors,
        "near_threshold_records": near_threshold,
        "quality_gates": {
            "frozen_model_hash_verified": True,
            "frozen_split_hash_verified": True,
            "stored_predictions_reproduced": True,
            "probabilities_reconstructed_from_feature_contributions": True,
            "all_38_records_diagnosed": len(diagnostics) == 38,
            "all_13_errors_queued": len(errors) == 13,
            "both_labels_share_capture_and_language_strata": strata_summary["both_labels_share_capture_and_language_strata"],
            "model_fit_operations_zero": True,
            "threshold_changes_zero": True,
            "labels_changed_zero": True,
        },
        "data_access": {
            "external_records_transformed": len(records),
            "frozen_fit_reference_rows_transformed_for_similarity_only": len(fit_rows),
            "frozen_internal_test_rows_loaded_or_transformed": 0,
            "auxiliary_rows_used": 0,
            "quarantine_rows_used": 0,
            "excluded_rows_used": access["excluded_rows_used"],
            "selection_access_audit": access,
        },
        "safety_contract": {
            "network_operations": 0,
            "candidate_domain_access_operations": 0,
            "model_fit_operations": 0,
            "threshold_changes": 0,
            "vectorizer_changes": 0,
            "labels_changed": 0,
            "benchmark_used_for_model_selection": False,
            "training_allowed": False,
            "deployment_allowed": False,
        },
        "interpretation_limits": [
            "Feature contributions and nearest neighbors describe model behavior, not causation or fraud evidence.",
            "Matched English and capture strata reduce but do not eliminate evidence-source or case-selection effects.",
            "This opened benchmark must not be used to tune a threshold or model and then be re-reported as independent evaluation.",
            "Primary and second review are AI reviews; independent human rereview is not claimed.",
        ],
        "next_gate": "Use findings only to predeclare future representation hypotheses and evaluate any selected challenger on new untouched external data; do not tune and re-score this benchmark.",
    }
    write_jsonl(outputs["diagnostics"], diagnostics)
    write_jsonl(outputs["errors"], errors)
    write_jsonl(outputs["near_threshold"], near_threshold)
    report["artifacts"] = {
        "diagnostics": {"path": str(outputs["diagnostics"]), "sha256": sha256_file(outputs["diagnostics"]), "record_count": len(diagnostics)},
        "error_queue": {"path": str(outputs["errors"]), "sha256": sha256_file(outputs["errors"]), "record_count": len(errors)},
        "near_threshold_queue": {"path": str(outputs["near_threshold"]), "sha256": sha256_file(outputs["near_threshold"]), "record_count": len(near_threshold)},
    }
    outputs["report"].write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(outputs["markdown"], report)
    print(json.dumps({
        "report": str(outputs["report"]),
        "report_sha256": sha256_file(outputs["report"]),
        "diagnostics_sha256": sha256_file(outputs["diagnostics"]),
        "error_queue_sha256": sha256_file(outputs["errors"]),
        "near_threshold_queue_sha256": sha256_file(outputs["near_threshold"]),
        "markdown_sha256": sha256_file(outputs["markdown"]),
        "counts": report["counts"],
        "matched_strata_analysis": report["matched_strata_analysis"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
