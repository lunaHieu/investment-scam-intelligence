"""Diagnose frozen external-pilot errors without fitting, tuning, or relabeling."""

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
    read_final_data,
    sha256_file,
    texts,
)


ANALYSIS_ID = "ISI_TEXT_BASELINE_V2_EXTERNAL_PILOT_ERROR_ANALYSIS_V1"
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


def frozen_inputs(external_registry_path: Path) -> dict[str, Path]:
    registry = load_json(external_registry_path)
    if registry.get("evaluation_id") != "ISI_TEXT_BASELINE_V2_EXTERNAL_PILOT_V1":
        raise ValueError("Unexpected external-pilot registry")
    root = external_registry_path.resolve().parents[2]
    roles = {
        **{name: item for name, item in registry.get("inputs", {}).items()},
        **{item["role"]: item for item in registry.get("outputs", [])},
    }
    required = {
        "model_registry",
        "reconciled_intake",
        "intake_validation_report",
        "results_json",
        "predictions_jsonl",
    }
    if not required.issubset(roles):
        raise ValueError("External registry is missing required frozen inputs")
    paths = {}
    for role in required:
        item = roles[role]
        path = resolve(root, item.get("path"))
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
        "report": output_dir / "external_pilot_error_analysis_v1.json",
        "diagnostics": output_dir / "external_pilot_diagnostics_v1.jsonl",
        "errors": output_dir / "external_pilot_error_queue_v1.jsonl",
        "markdown": output_dir / "external_pilot_error_analysis_v1.md",
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


def branch_label_confounding(records: list[dict]) -> dict[str, object]:
    table: dict[str, Counter] = defaultdict(Counter)
    for record in records:
        table[record["artifact"]["source_id"]][record["ground_truth_status"]] += 1
    rows = {
        source: {
            "CONFIRMED": counts["CONFIRMED"],
            "LEGITIMATE": counts["LEGITIMATE"],
        }
        for source, counts in sorted(table.items())
    }
    pure = all(not (values["CONFIRMED"] and values["LEGITIMATE"]) for values in rows.values())
    return {
        "source_by_label": rows,
        "every_collection_source_is_single_label": pure,
        "class_and_collection_branch_are_perfectly_confounded": pure and len(rows) > 1,
        "implication": (
            "Class metrics cannot separate label behavior from capture/source style on this pilot."
            if pure
            else "Both labels occur within at least one collection source."
        ),
    }


def subset_summary(items: list[dict]) -> dict[str, object]:
    return {
        "row_count": len(items),
        "score_label_1": numeric_summary([float(item["score_label_1"]) for item in items]),
        "surface_token_count": numeric_summary([float(item["surface_token_count"]) for item in items]),
        "unique_vectorizer_term_coverage": numeric_summary(
            [float(item["unique_vectorizer_term_coverage"]) for item in items]
        ),
        "nearest_fit_cosine_similarity": numeric_summary(
            [float(item["nearest_fit_cosine_similarity"]) for item in items]
        ),
        "nonzero_feature_count": numeric_summary(
            [float(item["nonzero_feature_count"]) for item in items]
        ),
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_markdown(path: Path, report: dict[str, object]) -> None:
    counts = report["counts"]
    confounding = report["collection_branch_confounding"]
    lines = [
        "# Text Baseline V2 – external pilot error analysis V1",
        "",
        "Phân tích này chỉ giải thích hành vi của model đóng băng. Không fit, không đổi threshold, "
        "không relabel và không dùng pilot để lựa chọn model.",
        "",
        "## Tóm tắt",
        "",
        f"- Lỗi: {counts['error_count']}/21 ({counts['false_positive_count']} FP, {counts['false_negative_count']} FN).",
        f"- Dự đoán label 1: {counts['predicted_label_1_count']}/21.",
        f"- Source/label confounding hoàn toàn: `{str(confounding['class_and_collection_branch_are_perfectly_confounded']).lower()}`.",
        "",
        "## Tám case sai",
        "",
        "| Case | Truth | Prediction | Score label 1 | Nearest Mendeley source | Similarity |",
        "|---|---|---:|---:|---|---:|",
    ]
    for item in report["errors"]:
        lines.append(
            f"| `{item['case_id']}` | `{item['ground_truth_status']}` | "
            f"`{item['predicted_source_label']}` | `{item['score_label_1']}` | "
            f"`{item['nearest_fit_source_dataset']}` | `{item['nearest_fit_cosine_similarity']}` |"
        )
    lines.extend(
        [
            "",
            "## Diễn giải an toàn",
            "",
            "- Feature contribution là liên hệ trong không gian TF-IDF, không phải bằng chứng nguyên nhân hoặc gian lận.",
            f"- {counts['errors_within_0_10_of_threshold']}/8 lỗi nằm trong khoảng 0,10 quanh threshold; "
            "không được chọn threshold mới từ 21 case này.",
            "- Cần benchmark mới có cả legitimate và confirmed trong từng nguồn/kiểu capture để tách source style khỏi nhãn.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--external-registry", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-at", required=True)
    args = parser.parse_args()
    paths = frozen_inputs(args.external_registry)
    outputs = prepare_output_paths(args.output_dir)

    intake = load_json(paths["reconciled_intake"])
    external_results = load_json(paths["results_json"])
    stored_predictions = load_jsonl(paths["predictions_jsonl"])
    records = sorted(intake["records"], key=lambda item: item["case_id"])
    if [item["case_id"] for item in records] != [item["case_id"] for item in stored_predictions]:
        raise ValueError("Stored predictions and sorted intake do not align")

    bundle = joblib.load(paths["model"])
    vectorizer = bundle["vectorizer"]
    classifier = bundle["classifier"]
    external_matrix = vectorizer.transform([item["artifact"]["text"] for item in records]).tocsr()
    probabilities = classifier.predict_proba(external_matrix)[:, 1]
    predictions = (probabilities >= THRESHOLD).astype(np.int64)
    truth = np.asarray([LABEL_MAP[item["ground_truth_status"]] for item in records], dtype=np.int64)
    for index, stored in enumerate(stored_predictions):
        if (
            int(stored["expected_source_label"]) != int(truth[index])
            or int(stored["predicted_source_label"]) != int(predictions[index])
            or not math.isclose(
                float(stored["score_label_1"]), float(probabilities[index]), rel_tol=0.0, abs_tol=5.1e-11
            )
        ):
            raise ValueError(f"Stored prediction mismatch: {stored.get('case_id')}")

    splits, access = read_final_data(paths["group_split_dataset"])
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
        term_count, matched_count, coverage = vocabulary_coverage(
            analyzer, vocabulary, record["artifact"]["text"]
        )
        nearest_index = int(nearest_indices[index])
        nearest = fit_rows[nearest_index] if nearest_index >= 0 else None
        contribution_sum = float(np.dot(row.data, coefficients[row.indices]))
        logit = intercept + contribution_sum
        reconstructed = 1.0 / (1.0 + math.exp(-logit))
        if not math.isclose(reconstructed, float(probabilities[index]), rel_tol=0.0, abs_tol=1e-10):
            raise ValueError(f"Contribution reconstruction failed: {record['case_id']}")
        expected = int(truth[index])
        predicted = int(predictions[index])
        item = {
            "case_id": record["case_id"],
            "ground_truth_status": record["ground_truth_status"],
            "expected_source_label": expected,
            "predicted_source_label": predicted,
            "correct": predicted == expected,
            "error_type": (
                None if predicted == expected else "false_positive" if expected == 0 else "false_negative"
            ),
            "score_label_1": round(float(probabilities[index]), 10),
            "distance_from_threshold": round(abs(float(probabilities[index]) - THRESHOLD), 10),
            "collection_source_id": record["artifact"]["source_id"],
            "surface_token_count": len(record["artifact"]["text"].split()),
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
            "feature_contributions": top_row_contributions(
                row.indices, row.data, coefficients, feature_names, limit=10
            ),
            "redacted_text_excerpt": redact_excerpt(record["artifact"]["text"], limit=320),
        }
        diagnostics.append(item)
    errors = [item for item in diagnostics if not item["correct"]]
    false_positives = [item for item in errors if item["error_type"] == "false_positive"]
    false_negatives = [item for item in errors if item["error_type"] == "false_negative"]
    true_positives = [
        item for item in diagnostics if item["correct"] and item["expected_source_label"] == 1
    ]
    true_negatives = [
        item for item in diagnostics if item["correct"] and item["expected_source_label"] == 0
    ]
    nearest_sources = Counter(item["nearest_fit_source_dataset"] for item in diagnostics)
    nearest_error_sources = Counter(item["nearest_fit_source_dataset"] for item in errors)
    report = {
        "analysis_id": ANALYSIS_ID,
        "run_at": args.run_at,
        "status": "FROZEN_EXTERNAL_DIAGNOSTIC_COMPLETE_NO_TUNING",
        "inputs": {
            role: {"path": str(path), "sha256": sha256_file(path)}
            for role, path in sorted(paths.items())
        },
        "counts": {
            "record_count": len(diagnostics),
            "correct_count": len(diagnostics) - len(errors),
            "error_count": len(errors),
            "false_positive_count": len(false_positives),
            "false_negative_count": len(false_negatives),
            "predicted_label_1_count": int(np.sum(predictions == 1)),
            "predicted_label_0_count": int(np.sum(predictions == 0)),
            "errors_within_0_10_of_threshold": sum(
                item["distance_from_threshold"] <= 0.10 for item in errors
            ),
        },
        "frozen_external_metrics": external_results["metrics"],
        "calibration": calibration_summary(truth, probabilities),
        "collection_branch_confounding": branch_label_confounding(records),
        "subsets": {
            "true_positive": subset_summary(true_positives),
            "true_negative": subset_summary(true_negatives),
            "false_positive": subset_summary(false_positives),
            "false_negative": subset_summary(false_negatives),
        },
        "nearest_fit_source_profile": {
            "all_records": dict(sorted(nearest_sources.items())),
            "errors": dict(sorted(nearest_error_sources.items())),
        },
        "error_feature_drivers": {
            "false_positive_toward_label_1": feature_driver_summary(
                false_positives, "toward_label_1"
            ),
            "false_positive_counterevidence_toward_label_0": feature_driver_summary(
                false_positives, "toward_label_0"
            ),
            "false_negative_toward_label_0": feature_driver_summary(
                false_negatives, "toward_label_0"
            ),
            "false_negative_counterevidence_toward_label_1": feature_driver_summary(
                false_negatives, "toward_label_1"
            ),
        },
        "errors": errors,
        "quality_gates": {
            "frozen_model_hash_verified": True,
            "frozen_split_hash_verified": True,
            "stored_predictions_reproduced": True,
            "probabilities_reconstructed_from_feature_contributions": True,
            "all_21_records_diagnosed": len(diagnostics) == 21,
            "all_8_errors_queued": len(errors) == 8,
            "model_fit_operations_zero": True,
            "threshold_changes_zero": True,
            "labels_changed_zero": True,
        },
        "data_access": {
            "external_records_transformed": len(records),
            "frozen_fit_reference_rows_transformed_for_similarity_only": len(fit_rows),
            "frozen_internal_test_rows_used": 0,
            "auxiliary_rows_used": access["auxiliary_rows_loaded_for_modeling"],
            "quarantine_rows_used": access["quarantine_rows_loaded_for_modeling"],
        },
        "safety_contract": {
            "network_operations": 0,
            "model_fit_operations": 0,
            "threshold_changes": 0,
            "vectorizer_changes": 0,
            "labels_changed": 0,
            "pilot_used_for_model_selection": False,
            "training_allowed": False,
            "deployment_allowed": False,
        },
        "interpretation_limits": [
            "Collection source and class are perfectly confounded in this 21-case pilot.",
            "Feature contributions and nearest neighbors describe model behavior, not causation or fraud evidence.",
            "This analysis must not be used to tune a threshold or model and re-report on the same pilot.",
            "The reconciled labels are AI-reviewed and human-owner adopted, without independent second-reviewer rereview.",
        ],
        "next_gate": (
            "Acquire an independently second-reviewed multi-source expansion containing both classes "
            "within comparable capture/source strata before any model-development decision."
        ),
    }
    write_jsonl(outputs["diagnostics"], diagnostics)
    write_jsonl(outputs["errors"], errors)
    report["artifacts"] = {
        "diagnostics": {
            "path": str(outputs["diagnostics"]),
            "sha256": sha256_file(outputs["diagnostics"]),
            "record_count": len(diagnostics),
        },
        "error_queue": {
            "path": str(outputs["errors"]),
            "sha256": sha256_file(outputs["errors"]),
            "record_count": len(errors),
        },
    }
    outputs["report"].write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_markdown(outputs["markdown"], report)
    print(
        json.dumps(
            {
                "report": str(outputs["report"]),
                "report_sha256": sha256_file(outputs["report"]),
                "diagnostics_sha256": sha256_file(outputs["diagnostics"]),
                "error_queue_sha256": sha256_file(outputs["errors"]),
                "markdown_sha256": sha256_file(outputs["markdown"]),
                "counts": report["counts"],
                "collection_branch_confounding": report["collection_branch_confounding"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
