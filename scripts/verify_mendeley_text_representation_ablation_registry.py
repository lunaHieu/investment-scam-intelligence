"""Verify the frozen Mendeley text-representation ablation and its artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_REPRESENTATIONS = {
    "word_1_2",
    "char_wb_3_5",
    "char_3_5",
    "word_1_2_plus_char_wb_3_5",
}
EXPECTED_TEST_REPRESENTATIONS = {
    "word_1_2",
    "word_1_2_plus_char_wb_3_5",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_close(actual, expected, label: str) -> None:
    if abs(float(actual) - float(expected)) > 1e-9:
        raise ValueError(f"{label} mismatch: {actual} != {expected}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        type=Path,
        default=(
            ROOT
            / "registry"
            / "models"
            / "mendeley_text_representation_ablation_v1.json"
        ),
    )
    args = parser.parse_args()

    registry = load_json(args.registry)
    assert registry["analysis_id"] == "MENDELEY_TEXT_REPRESENTATION_ABLATION_V1"
    assert registry["status"] == "FROZEN_RESEARCH_ABLATION_NOT_FOR_DEPLOYMENT"
    assert registry["data_contract"]["partition_counts"] == {
        "train": 11344,
        "validation": 2429,
        "test": 2429,
    }
    assert registry["data_contract"]["split_group_cross_partition_count"] == 0
    assert registry["representation_contract"]["source_dataset_in_feature_matrix"] is False
    assert registry["representation_contract"]["raw_files_modified"] is False
    assert registry["representation_contract"]["network_operations"] == 0
    assert registry["selection_policy"]["all_classifier_hyperparameters_frozen"] is True
    assert registry["selection_policy"]["test_used_for_vectorizer_or_model_fitting"] is False
    assert (
        registry["selection_policy"]["test_used_for_hyperparameter_or_representation_selection"]
        is False
    )
    assert set(registry["selection_policy"]["validation_candidates"]) == EXPECTED_REPRESENTATIONS
    assert "char_3_5" not in registry["selection_policy"][
        "promotion_eligible_representations"
    ]
    assert set(
        registry["selection_policy"]["representations_opened_on_internal_test"]
    ) == EXPECTED_TEST_REPRESENTATIONS
    assert registry["decision"]["qualifies_as_internal_research_candidate"] is False
    assert registry["decision"]["promote_to_primary_internal_baseline"] is False
    assert registry["decision"]["deployment_allowed"] is False

    artifacts = {item["role"]: item for item in registry["artifacts"]}
    assert set(artifacts) == {
        "group_split_dataset",
        "ablation_results",
        "test_predictions",
    }
    for item in artifacts.values():
        path = Path(item["path"])
        if not path.is_file():
            raise FileNotFoundError(path)
        actual_hash = sha256_file(path)
        if actual_hash != item["sha256"]:
            raise ValueError(f"SHA-256 mismatch for {item['role']}: {actual_hash}")

    results = load_json(Path(artifacts["ablation_results"]["path"]))
    assert results["analysis_id"] == registry["analysis_id"]
    assert results["run_at"] == registry["run_at"]
    assert results["data"]["input_sha256"] == registry["data_contract"][
        "derived_split_sha256"
    ]
    assert results["data"]["partition_counts"] == registry["data_contract"][
        "partition_counts"
    ]
    assert set(results["representations"]) == EXPECTED_REPRESENTATIONS
    assert results["feature_contract"]["source_dataset_in_feature_matrix"] is False
    assert results["feature_contract"]["raw_files_modified"] is False
    assert results["feature_contract"]["network_operations"] == 0
    assert results["selection_policy"]["test_used_for_hyperparameter_or_representation_selection"] is False
    assert set(
        results["selection_policy"]["representations_opened_on_internal_test"]
    ) == EXPECTED_TEST_REPRESENTATIONS
    assert results["selection_policy"]["selected_representation_on_validation"] == (
        registry["selection_policy"]["selected_representation_on_validation"]
    )
    assert results["decision"]["promote_to_primary_internal_baseline"] is False
    assert results["decision"]["deployment_allowed"] is False

    for name, report in results["representations"].items():
        assert report["frozen_classifier"] == {
            "C": 2.0,
            "class_weight": None,
            "solver": "liblinear",
            "threshold": 0.5,
        }
        assert report["feature_count"] == registry["metrics"][name]["feature_count"]
        assert_close(
            report["validation"]["macro_f1"],
            registry["metrics"][name]["validation_macro_f1"],
            f"{name} validation Macro-F1",
        )
        assert_close(
            report["validation_source_predictability_diagnostic"]["validation"][
                "macro_f1"
            ],
            registry["metrics"][name]["validation_source_predictability_macro_f1"],
            f"{name} source predictability Macro-F1",
        )
        if name in EXPECTED_TEST_REPRESENTATIONS:
            assert "test" in report and "leave_one_source_out" in report
            assert_close(
                report["test"]["macro_f1"],
                registry["metrics"][name]["test_macro_f1"],
                f"{name} test Macro-F1",
            )
        else:
            assert "test" not in report and "leave_one_source_out" not in report

    frozen_text = load_json(ROOT / "registry" / "models" / "text_baseline_v1.json")
    baseline = results["representations"]["word_1_2"]
    baseline_comparisons = [
        (baseline["validation"]["f1_label_1"], frozen_text["metrics"]["validation_f1_label_1"]),
        (baseline["test"]["accuracy"], frozen_text["metrics"]["test_accuracy"]),
        (baseline["test"]["f1_label_1"], frozen_text["metrics"]["test_f1_label_1"]),
        (baseline["test"]["macro_f1"], frozen_text["metrics"]["test_macro_f1"]),
        (
            baseline["test"]["balanced_accuracy"],
            frozen_text["metrics"]["test_balanced_accuracy"],
        ),
        (
            baseline["leave_one_source_out_mean_across_sources"]["macro_f1"],
            frozen_text["metrics"]["leave_one_source_out_mean_macro_f1"],
        ),
    ]
    for actual, expected in baseline_comparisons:
        assert_close(actual, expected, "frozen word baseline reproduction")

    template = results["near_duplicate_diagnostic"][
        "normalized_template_partition_audit"
    ]
    registered_template = registry["data_contract"][
        "normalized_template_partition_audit"
    ]
    assert template["cross_partition_normalized_template_count"] == registered_template[
        "cross_partition_template_count"
    ]
    assert template["affected_row_count"] == registered_template["affected_row_count"]
    assert template["affected_sources"] == registered_template["affected_sources"]
    assert template["normalizer_used_to_build_current_split"] is False

    paired = results["paired_test_group_bootstrap_selected_vs_word_baseline"]
    assert paired["unit"] == "split_group_id"
    assert paired["cluster_count"] == registry["paired_group_bootstrap"]["cluster_count"]
    assert paired["largest_cluster_rows"] == registry["paired_group_bootstrap"][
        "largest_cluster_rows"
    ]
    assert paired["ci_lower_bound_gt_0"] is False

    split_test = {}
    with Path(artifacts["group_split_dataset"]["path"]).open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        for row in csv.DictReader(handle):
            if row["partition"] == "test":
                split_test[row["record_id"]] = row

    predictions_path = Path(artifacts["test_predictions"]["path"])
    prediction_ids = set()
    group_counts = Counter()
    with predictions_path.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            record_id = record["record_id"]
            if record_id in prediction_ids:
                raise ValueError(f"Duplicate prediction record_id: {record_id}")
            prediction_ids.add(record_id)
            source = split_test[record_id]
            assert record["partition"] == "test"
            assert record["split_group_id"] == source["split_group_id"]
            assert record["source_dataset"] == source["source_dataset"]
            assert record["source_label"] == int(source["label"])
            assert set(record["predictions"]) == EXPECTED_TEST_REPRESENTATIONS
            for prediction in record["predictions"].values():
                assert prediction["predicted_label"] in {0, 1}
                assert 0.0 <= prediction["score_label_1"] <= 1.0
            group_counts[record["split_group_id"]] += 1
    assert prediction_ids == set(split_test)
    assert len(prediction_ids) == registry["data_contract"]["partition_counts"]["test"]
    assert len(group_counts) == registry["paired_group_bootstrap"]["cluster_count"]
    assert max(group_counts.values()) == registry["paired_group_bootstrap"][
        "largest_cluster_rows"
    ]

    print(
        "Mendeley text-representation ablation registry valid: hashes and split rows match, "
        "2,429 unique predictions checked, frozen baseline reproduced, no promotion."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
