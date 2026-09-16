"""Verify the frozen Mendeley source-balance ablation and its artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_STRATEGIES = {
    "unweighted",
    "sqrt_inverse_source_frequency",
    "inverse_source_frequency",
    "sqrt_inverse_source_label_frequency",
    "inverse_source_label_frequency",
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
        default=ROOT / "registry" / "models" / "mendeley_source_balance_ablation_v1.json",
    )
    args = parser.parse_args()

    registry = load_json(args.registry)
    assert registry["analysis_id"] == "MENDELEY_SOURCE_BALANCE_ABLATION_V1"
    assert registry["status"] == "FROZEN_RESEARCH_ABLATION_NOT_FOR_DEPLOYMENT"
    assert registry["data_contract"]["partition_counts"] == {
        "train": 11344,
        "validation": 2429,
        "test": 2429,
    }
    assert registry["data_contract"]["split_group_cross_partition_count"] == 0
    assert registry["model_contract"]["source_dataset_in_feature_matrix"] is False
    assert registry["model_contract"]["raw_files_modified"] is False
    assert registry["model_contract"]["network_operations"] == 0
    assert registry["selection_policy"]["test_used_for_vectorizer_or_model_fitting"] is False
    assert registry["selection_policy"]["test_used_for_strategy_selection"] is False
    assert registry["selection_policy"]["selected_strategy_on_validation"] == "unweighted"
    assert registry["decision"]["promote_to_primary_internal_baseline"] is False
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
    assert set(results["strategies"]) == EXPECTED_STRATEGIES
    assert results["model_contract"]["source_dataset_in_feature_matrix"] is False
    assert results["selection_policy"]["test_used_for_strategy_selection"] is False
    assert results["selection_policy"]["selected_strategy_on_validation"] == "unweighted"
    assert results["decision"]["promote_to_primary_internal_baseline"] is False

    equalized = results["strategies"]["inverse_source_frequency"]["weight_profile"]
    source_weight_totals = list(equalized["total_weight_by_source_dataset"].values())
    assert max(source_weight_totals) - min(source_weight_totals) < 1e-9

    frozen_text = load_json(ROOT / "registry" / "models" / "text_baseline_v1.json")
    baseline = results["strategies"]["unweighted"]
    comparisons = [
        (baseline["validation"]["f1_label_1"], frozen_text["metrics"]["validation_f1_label_1"]),
        (baseline["test"]["accuracy"], frozen_text["metrics"]["test_accuracy"]),
        (baseline["test"]["f1_label_1"], frozen_text["metrics"]["test_f1_label_1"]),
        (baseline["test"]["macro_f1"], frozen_text["metrics"]["test_macro_f1"]),
        (baseline["test"]["balanced_accuracy"], frozen_text["metrics"]["test_balanced_accuracy"]),
        (
            baseline["leave_one_source_out_mean_across_sources"]["f1_label_1"],
            frozen_text["metrics"]["leave_one_source_out_mean_f1_label_1"],
        ),
        (
            baseline["leave_one_source_out_mean_across_sources"]["macro_f1"],
            frozen_text["metrics"]["leave_one_source_out_mean_macro_f1"],
        ),
        (
            baseline["leave_one_source_out_mean_across_sources"]["balanced_accuracy"],
            frozen_text["metrics"]["leave_one_source_out_mean_balanced_accuracy"],
        ),
    ]
    for actual, expected in comparisons:
        if abs(actual - expected) > 1e-9:
            raise ValueError(f"Unweighted baseline reproduction mismatch: {actual} != {expected}")

    line_count = 0
    record_ids = set()
    with Path(artifacts["test_predictions"]["path"]).open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            line_count += 1
            record_ids.add(record["record_id"])
            assert record["partition"] == "test"
            assert record["source_label"] in {0, 1}
            assert set(record["predictions"]) == EXPECTED_STRATEGIES
    assert line_count == registry["data_contract"]["partition_counts"]["test"]
    assert len(record_ids) == line_count

    print(
        "Mendeley source-balance ablation registry valid: hashes match, weights checked, "
        "2,429 unique test predictions, frozen text baseline reproduced, no promotion."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
