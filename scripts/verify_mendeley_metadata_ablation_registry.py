"""Verify the frozen Mendeley metadata-ablation registry and artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VARIANTS = {
    "text_only",
    "account_behaviour_only_values",
    "content_statistics_only_values",
    "all_metadata_only_values",
    "all_metadata_only_with_missingness",
    "text_plus_account_behaviour_values",
    "text_plus_content_statistics_values",
    "text_plus_all_metadata_values",
    "text_plus_all_metadata_with_missingness",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        type=Path,
        default=ROOT / "registry" / "models" / "mendeley_metadata_ablation_v1.json",
    )
    args = parser.parse_args()

    registry = load_json(args.registry)
    assert registry["analysis_id"] == "MENDELEY_METADATA_ABLATION_V1"
    assert registry["status"] == "FROZEN_RESEARCH_ABLATION_NOT_FOR_DEPLOYMENT"
    assert registry["data_contract"]["partition_counts"] == {
        "train": 11344,
        "validation": 2429,
        "test": 2429,
    }
    assert registry["data_contract"]["split_group_cross_partition_count"] == 0
    assert registry["feature_safety"]["source_dataset_used_as_predictive_feature"] is False
    assert registry["feature_safety"]["network_operations"] == 0
    assert registry["feature_safety"]["raw_files_modified"] is False
    assert registry["selection_policy"]["test_used_for_feature_fitting"] is False
    assert registry["selection_policy"]["test_used_for_hyperparameter_or_variant_selection"] is False
    assert registry["decision"]["promote_metadata_to_primary_baseline"] is False
    assert registry["decision"]["deployment_allowed"] is False

    artifacts = {item["role"]: item for item in registry["artifacts"]}
    assert set(artifacts) == {"group_split_dataset", "ablation_results", "test_predictions"}
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
    assert results["data"]["input_sha256"] == registry["data_contract"]["derived_split_sha256"]
    assert results["data"]["partition_counts"] == registry["data_contract"]["partition_counts"]
    assert results["data"]["split_group_cross_partition_count"] == 0
    assert set(results["variants"]) == EXPECTED_VARIANTS
    assert results["selection_policy"]["test_used_for_feature_fitting"] is False
    assert results["selection_policy"]["test_used_for_hyperparameter_or_variant_selection"] is False
    assert results["metadata_contract"]["source_dataset_predictive_use"] is False
    assert results["decision"]["promote_metadata_to_primary_baseline"] is False
    assert (
        results["selection_policy"]["selected_combined_variant_on_validation"]
        == registry["selection_policy"]["selected_combined_variant_on_validation"]
    )

    frozen_text = load_json(ROOT / "registry" / "models" / "text_baseline_v1.json")
    text = results["variants"]["text_only"]
    comparisons = [
        (text["validation"]["f1_label_1"], frozen_text["metrics"]["validation_f1_label_1"]),
        (text["test"]["accuracy"], frozen_text["metrics"]["test_accuracy"]),
        (text["test"]["f1_label_1"], frozen_text["metrics"]["test_f1_label_1"]),
        (text["test"]["macro_f1"], frozen_text["metrics"]["test_macro_f1"]),
        (text["test"]["balanced_accuracy"], frozen_text["metrics"]["test_balanced_accuracy"]),
        (
            text["leave_one_source_out_mean_across_sources"]["f1_label_1"],
            frozen_text["metrics"]["leave_one_source_out_mean_f1_label_1"],
        ),
        (
            text["leave_one_source_out_mean_across_sources"]["macro_f1"],
            frozen_text["metrics"]["leave_one_source_out_mean_macro_f1"],
        ),
        (
            text["leave_one_source_out_mean_across_sources"]["balanced_accuracy"],
            frozen_text["metrics"]["leave_one_source_out_mean_balanced_accuracy"],
        ),
    ]
    for actual, expected in comparisons:
        if abs(actual - expected) > 1e-9:
            raise ValueError(f"Text baseline reproduction mismatch: {actual} != {expected}")

    line_count = 0
    record_ids = set()
    prediction_path = Path(artifacts["test_predictions"]["path"])
    with prediction_path.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            line_count += 1
            record_ids.add(record["record_id"])
            assert record["partition"] == "test"
            assert record["source_label"] in {0, 1}
            assert set(record["predictions"]) == EXPECTED_VARIANTS
    assert line_count == registry["data_contract"]["partition_counts"]["test"]
    assert len(record_ids) == line_count

    print(
        "Mendeley metadata ablation registry valid: input/output hashes match, "
        "2,429 unique test predictions, frozen text baseline reproduced, metadata not promoted."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
