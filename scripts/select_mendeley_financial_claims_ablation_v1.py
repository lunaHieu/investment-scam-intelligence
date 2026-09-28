"""Run the frozen validation-only Financial Claims V4 feature ablation.

The protocol, group_split_v2 CSV, and V4 feature JSONL are all hash-pinned.
Only train text is fit and only validation is scored. Test, auxiliary, and
quarantine text and labels are not retained, transformed, or evaluated.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix, hstack

from mendeley_text_baseline_v2_common import (
    EXPECTED_SOURCES,
    EXPECTED_SPLIT_SHA256,
    LABEL_SEMANTICS,
    RANDOM_STATE,
    THRESHOLD,
    VECTORIZER_CONFIG,
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


PROTOCOL_ID = "MENDELEY_FINANCIAL_CLAIMS_ABLATION_V1_PROTOCOL"
SELECTION_ID = "MENDELEY_FINANCIAL_CLAIMS_ABLATION_V1_VALIDATION_SELECTION"
EXPECTED_PROTOCOL_SHA256 = "e9fa5fa6dbcdf51e93671f327af5606141a7b1fd639102cf52f6eadb43555de2"
EXPECTED_FEATURE_SHA256 = "8e222b3cace3f6c922da8044c34e9481badb73ac52fdc8b44b64449f1656badc"
EXPECTED_FEATURE_VERSION = "MENDELEY_FINANCIAL_CLAIMS_V4"
EXPECTED_FEATURE_COUNTS = {"train": 3_916, "validation": 838}
CLASSIFIER_CONFIG = {"C": 2.0, "class_weight": None}
CLAIM_COLUMNS = (
    "has_return_rate",
    "has_return_multiple",
    "has_money_amount",
    "has_guaranteed_return",
    "has_no_risk",
    "has_urgency_scarcity",
    "has_passive_or_easy_income",
    "has_recruitment_reward",
    "has_payment_or_transfer_request",
    "has_advance_fee_or_withdrawal",
    "has_crypto_investment_or_payment",
)
VARIANTS = (
    "text_only",
    "text_plus_financial_claim_presence",
    "financial_claim_presence_only",
)
PRIMARY_MINIMUM_IMPROVEMENT = 0.01
MAXIMUM_SOURCE_DROP = 0.01
FORBIDDEN_KEYS = {
    "label",
    "source_label",
    "source_dataset",
    "original_partition",
    "ground_truth_status",
    "label_confidence",
    "review_notes",
    "verification_status",
}


def load_frozen_protocol(path: Path) -> dict:
    actual_hash = sha256_file(path)
    if actual_hash != EXPECTED_PROTOCOL_SHA256:
        raise ValueError(
            "Ablation protocol SHA-256 mismatch: "
            f"expected {EXPECTED_PROTOCOL_SHA256}, got {actual_hash}"
        )
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("protocol_id") != PROTOCOL_ID:
        raise ValueError("Unexpected ablation protocol ID")
    if protocol.get("status") != "FROZEN_BEFORE_VALIDATION_SELECTION":
        raise ValueError("Ablation protocol is not frozen before selection")
    declared_columns = tuple(
        protocol.get("financial_claim_feature_contract", {}).get("columns", [])
    )
    if declared_columns != CLAIM_COLUMNS:
        raise ValueError("Protocol feature columns differ from the frozen implementation")
    declared_variants = tuple(
        item.get("variant_id") for item in protocol.get("predeclared_variants", [])
    )
    if declared_variants != VARIANTS:
        raise ValueError("Protocol variants differ from the frozen implementation")
    gates = protocol.get("selection_policy", {}).get("challenger_promotion_gates", {})
    if gates.get("primary_metric_minimum_absolute_improvement") != PRIMARY_MINIMUM_IMPROVEMENT:
        raise ValueError("Protocol primary improvement threshold mismatch")
    if gates.get("maximum_allowed_macro_f1_drop_for_any_source") != MAXIMUM_SOURCE_DROP:
        raise ValueError("Protocol maximum per-source drop mismatch")
    return protocol


def load_feature_records(
    path: Path,
    *,
    require_frozen_hash: bool = True,
    expected_counts: dict[str, int] | None = None,
) -> tuple[dict[str, dict], dict]:
    actual_hash = sha256_file(path)
    if require_frozen_hash and actual_hash != EXPECTED_FEATURE_SHA256:
        raise ValueError(
            "Financial Claims feature SHA-256 mismatch: "
            f"expected {EXPECTED_FEATURE_SHA256}, got {actual_hash}"
        )
    expected = expected_counts or EXPECTED_FEATURE_COUNTS
    records: dict[str, dict] = {}
    counts: Counter[str] = Counter()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError(f"Feature line {line_number} is not a JSON object")
            if FORBIDDEN_KEYS.intersection(record):
                raise ValueError(f"Feature line {line_number} contains a forbidden top-level key")
            features = record.get("features")
            if not isinstance(features, dict) or FORBIDDEN_KEYS.intersection(features):
                raise ValueError(f"Feature line {line_number} has an invalid feature container")
            record_id = str(record.get("record_id") or "")
            partition = str(record.get("partition") or "")
            if not record_id or record_id in records:
                raise ValueError(f"Feature line {line_number} has a missing or duplicate record_id")
            if partition not in expected:
                raise ValueError(f"Feature line {line_number} contains prohibited partition {partition!r}")
            if record.get("feature_version") != EXPECTED_FEATURE_VERSION:
                raise ValueError(f"Feature line {line_number} has the wrong feature version")
            for column in CLAIM_COLUMNS:
                if type(features.get(column)) is not bool:
                    raise ValueError(
                        f"Feature line {line_number} column {column} must be boolean"
                    )
            records[record_id] = record
            counts[partition] += 1
    if dict(counts) != expected:
        raise ValueError(f"Financial Claims partition counts mismatch: {dict(counts)}")
    return records, {
        "feature_sha256": actual_hash,
        "feature_partition_counts": {name: counts[name] for name in expected},
        "test_feature_rows_loaded": 0,
        "auxiliary_feature_rows_loaded": 0,
        "quarantine_feature_rows_loaded": 0,
    }


def claim_matrix(rows: list[dict[str, str]], features_by_id: dict[str, dict]) -> csr_matrix:
    values = []
    for row in rows:
        record_id = row["record_id"]
        record = features_by_id.get(record_id)
        if record is None:
            raise ValueError(f"Missing Financial Claims record: {record_id}")
        if record.get("partition") != row["partition"]:
            raise ValueError(f"Partition mismatch for Financial Claims record: {record_id}")
        if record.get("split_group_id") != row["split_group_id"]:
            raise ValueError(f"Split-group mismatch for Financial Claims record: {record_id}")
        feature_values = record["features"]
        values.append([float(feature_values[column]) for column in CLAIM_COLUMNS])
    return csr_matrix(np.asarray(values, dtype=np.float64))


def feature_support(matrix: csr_matrix, row_count: int) -> dict[str, dict]:
    counts = np.asarray(matrix.sum(axis=0)).ravel()
    return {
        column: {
            "true_count": int(count),
            "true_ratio": round(float(count / max(1, row_count)), 6),
        }
        for column, count in zip(CLAIM_COLUMNS, counts, strict=True)
    }


def promotion_decision(baseline: dict, challenger: dict) -> dict:
    baseline_summary = baseline["validation_source_summary"]
    challenger_summary = challenger["validation_source_summary"]
    primary_delta = round(
        challenger_summary["unweighted_mean_macro_f1_across_sources"]
        - baseline_summary["unweighted_mean_macro_f1_across_sources"],
        6,
    )
    pooled_delta = round(
        challenger["validation"]["macro_f1"] - baseline["validation"]["macro_f1"],
        6,
    )
    worst_delta = round(
        challenger_summary["worst_source_macro_f1"]
        - baseline_summary["worst_source_macro_f1"],
        6,
    )
    source_deltas = {
        source: round(
            challenger["validation_by_source_dataset"][source]["macro_f1"]
            - baseline["validation_by_source_dataset"][source]["macro_f1"],
            6,
        )
        for source in sorted(baseline["validation_by_source_dataset"])
    }
    gates = {
        "primary_metric_improves_by_at_least_0_01": (
            primary_delta >= PRIMARY_MINIMUM_IMPROVEMENT
        ),
        "worst_source_macro_f1_not_decreased": worst_delta >= 0.0,
        "pooled_macro_f1_not_decreased": pooled_delta >= 0.0,
        "no_source_macro_f1_drop_exceeds_0_01": min(source_deltas.values())
        >= -MAXIMUM_SOURCE_DROP,
    }
    passes = all(gates.values())
    return {
        "primary_metric_delta": primary_delta,
        "worst_source_macro_f1_delta": worst_delta,
        "pooled_macro_f1_delta": pooled_delta,
        "per_source_macro_f1_deltas": source_deltas,
        "promotion_gates": gates,
        "passes_all_promotion_gates": passes,
        "selected_variant": (
            "text_plus_financial_claim_presence" if passes else "text_only"
        ),
    }


def runtime_versions() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "scikit_learn": importlib.metadata.version("scikit-learn"),
        "numpy": importlib.metadata.version("numpy"),
        "scipy": importlib.metadata.version("scipy"),
    }


def run_selection(
    split_path: Path,
    feature_path: Path,
    protocol_path: Path,
    *,
    run_at: str,
) -> dict:
    protocol = load_frozen_protocol(protocol_path)
    protocol_hash_before = sha256_file(protocol_path)
    split_hash_before = sha256_file(split_path)
    feature_hash_before = sha256_file(feature_path)
    splits, split_access = read_selection_data(split_path)
    features_by_id, feature_access = load_feature_records(feature_path)
    train_rows = splits["train"]
    validation_rows = splits["validation"]
    expected_ids = {row["record_id"] for row in train_rows + validation_rows}
    if set(features_by_id) != expected_ids:
        raise ValueError("Financial Claims records do not exactly cover train and validation")

    vectorizer = make_vectorizer()
    train_text_matrix = vectorizer.fit_transform(texts(train_rows)).tocsr()
    validation_text_matrix = vectorizer.transform(texts(validation_rows)).tocsr()
    train_claim_matrix = claim_matrix(train_rows, features_by_id)
    validation_claim_matrix = claim_matrix(validation_rows, features_by_id)
    train_combined_matrix = hstack(
        [train_text_matrix, train_claim_matrix], format="csr"
    )
    validation_combined_matrix = hstack(
        [validation_text_matrix, validation_claim_matrix], format="csr"
    )

    matrices = {
        "text_only": (train_text_matrix, validation_text_matrix),
        "text_plus_financial_claim_presence": (
            train_combined_matrix,
            validation_combined_matrix,
        ),
        "financial_claim_presence_only": (
            train_claim_matrix,
            validation_claim_matrix,
        ),
    }
    train_truth = labels(train_rows)
    variant_reports: dict[str, dict] = {}
    for variant_id in VARIANTS:
        train_matrix, validation_matrix = matrices[variant_id]
        classifier = make_classifier(CLASSIFIER_CONFIG)
        fit_classifier(classifier, train_matrix, train_truth)
        validation, predictions, probabilities = evaluate_classifier(
            classifier, validation_matrix, validation_rows
        )
        by_source = evaluate_by_source(validation_rows, predictions, probabilities)
        report = {
            "variant_id": variant_id,
            "promotion_eligible": variant_id != "financial_claim_presence_only",
            "feature_count": int(train_matrix.shape[1]),
            "train_matrix_nnz": int(train_matrix.nnz),
            "validation": validation,
            "validation_by_source_dataset": by_source,
            "validation_source_summary": source_summary(by_source),
        }
        if variant_id == "text_plus_financial_claim_presence":
            claim_coefficients = classifier.coef_[0][-len(CLAIM_COLUMNS) :]
            report["financial_claim_coefficients"] = {
                column: round(float(value), 8)
                for column, value in zip(CLAIM_COLUMNS, claim_coefficients, strict=True)
            }
        elif variant_id == "financial_claim_presence_only":
            report["financial_claim_coefficients"] = {
                column: round(float(value), 8)
                for column, value in zip(CLAIM_COLUMNS, classifier.coef_[0], strict=True)
            }
        variant_reports[variant_id] = report

    decision = promotion_decision(
        variant_reports["text_only"],
        variant_reports["text_plus_financial_claim_presence"],
    )
    split_hash_after = sha256_file(split_path)
    feature_hash_after = sha256_file(feature_path)
    protocol_hash_after = sha256_file(protocol_path)
    validation_sources = {row["source_dataset"] for row in validation_rows}
    quality_gates = {
        "protocol_hash_matches_frozen_value": protocol_hash_before
        == EXPECTED_PROTOCOL_SHA256,
        "protocol_unchanged_during_selection": protocol_hash_after
        == protocol_hash_before,
        "split_hash_matches_frozen_value": split_hash_before == EXPECTED_SPLIT_SHA256,
        "split_unchanged_during_selection": split_hash_after == split_hash_before,
        "feature_hash_matches_frozen_value": feature_hash_before
        == EXPECTED_FEATURE_SHA256,
        "feature_artifact_unchanged_during_selection": feature_hash_after
        == feature_hash_before,
        "train_rows_loaded_exact": len(train_rows) == EXPECTED_FEATURE_COUNTS["train"],
        "validation_rows_loaded_exact": len(validation_rows)
        == EXPECTED_FEATURE_COUNTS["validation"],
        "feature_coverage_exact": set(features_by_id) == expected_ids,
        "all_four_sources_present_in_validation": validation_sources == EXPECTED_SOURCES,
        "test_text_rows_loaded_zero": split_access["loaded_text_rows"]["test"] == 0,
        "test_text_transformed_zero": split_access["test_text_transformed"] == 0,
        "test_labels_used_zero": split_access["test_labels_used"] == 0,
        "auxiliary_and_quarantine_rows_used_zero": split_access["excluded_rows_used"] == 0,
        "test_feature_rows_loaded_zero": feature_access["test_feature_rows_loaded"] == 0,
        "all_variants_predeclared": tuple(variant_reports) == VARIANTS,
        "source_dataset_not_in_feature_matrix": True,
        "review_or_evidence_fields_not_in_feature_matrix": True,
    }
    failed = sorted(name for name, passed in quality_gates.items() if not passed)
    if failed:
        raise ValueError("Financial Claims ablation quality gates failed: " + ", ".join(failed))

    return {
        "selection_id": SELECTION_ID,
        "protocol_id": PROTOCOL_ID,
        "run_at": run_at,
        "status": "FROZEN_VALIDATION_SELECTION_TEST_UNOPENED",
        "label_semantics": LABEL_SEMANTICS,
        "data": {
            "split_file_name": split_path.name,
            "input_split_sha256": split_hash_before,
            "feature_file_name": feature_path.name,
            "feature_artifact_sha256": feature_hash_before,
            "protocol_file_name": protocol_path.name,
            "protocol_sha256": protocol_hash_before,
            "train_row_count": len(train_rows),
            "validation_row_count": len(validation_rows),
            "train_source_label_counts": source_label_counts(train_rows),
            "validation_source_label_counts": source_label_counts(validation_rows),
        },
        "data_access": {
            "split": split_access,
            "financial_claim_features": feature_access,
            "test_opened": False,
            "test_metrics_created": False,
            "auxiliary_or_quarantine_rows_used": False,
        },
        "feature_contract": {
            "text_vectorizer": VECTORIZER_CONFIG,
            "text_vocabulary_size": len(vectorizer.vocabulary_),
            "financial_claim_columns": list(CLAIM_COLUMNS),
            "financial_claim_encoding": "raw boolean 0/1",
            "financial_claim_scaler": None,
            "post_stack_normalization": None,
            "train_support": feature_support(train_claim_matrix, len(train_rows)),
            "validation_support": feature_support(
                validation_claim_matrix, len(validation_rows)
            ),
        },
        "classifier_contract": {
            "type": "LogisticRegression",
            "C": CLASSIFIER_CONFIG["C"],
            "class_weight": CLASSIFIER_CONFIG["class_weight"],
            "solver": "liblinear",
            "max_iter": 2_000,
            "random_state": RANDOM_STATE,
            "threshold": THRESHOLD,
        },
        "predeclared_variants": list(VARIANTS),
        "variant_results": variant_reports,
        "selection_policy": protocol["selection_policy"],
        "decision": {
            **decision,
            "qualifies_as_validation_selected_research_candidate": decision[
                "passes_all_promotion_gates"
            ],
            "test_evaluation_allowed": False,
            "deployment_allowed": False,
        },
        "quality_gates": quality_gates,
        "runtime": runtime_versions(),
        "safety_contract": {
            "raw_files_modified": False,
            "split_file_modified": False,
            "feature_artifact_modified": False,
            "protocol_modified": False,
            "network_operations": 0,
            "model_artifact_created": False,
            "test_opened": False,
            "test_predictions_created": False,
        },
    }


def write_json(path: Path, value: dict, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite frozen selection: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-at", default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    output_resolved = args.output.resolve()
    for source in (args.input, args.features, args.protocol):
        if source.resolve() == output_resolved:
            raise ValueError("Selection output must differ from every frozen input")
    run_at = args.run_at or datetime.now(timezone.utc).isoformat()
    report = run_selection(
        args.input,
        args.features,
        args.protocol,
        run_at=run_at,
    )
    write_json(args.output, report, overwrite=args.overwrite)
    print(
        json.dumps(
            {
                "selection_id": report["selection_id"],
                "status": report["status"],
                "selected_variant": report["decision"]["selected_variant"],
                "promotion_gates": report["decision"]["promotion_gates"],
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
