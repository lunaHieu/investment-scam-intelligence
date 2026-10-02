import tempfile
import unittest
from pathlib import Path

from scripts.select_mendeley_text_challenger_v2 import (
    BASELINE_ID,
    CHALLENGER_ID,
    combine_and_normalize,
    paired_group_bootstrap,
    prepare_output_paths,
    promotion_decision,
)


class MendeleyTextChallengerV2Tests(unittest.TestCase):
    def test_combined_matrix_is_row_normalized(self):
        import numpy as np
        from scipy import sparse

        matrix = combine_and_normalize(
            sparse.csr_matrix([[3.0, 4.0], [0.0, 2.0]]),
            sparse.csr_matrix([[0.0, 5.0], [2.0, 0.0]]),
        )
        norms = np.sqrt(matrix.multiply(matrix).sum(axis=1)).A1
        np.testing.assert_allclose(norms, np.ones(2))

    def test_bootstrap_is_grouped_and_deterministic(self):
        import numpy as np

        truth = np.asarray([0, 0, 1, 1])
        baseline = np.asarray([0, 1, 0, 1])
        challenger = np.asarray([0, 0, 1, 1])
        first = paired_group_bootstrap(baseline, challenger, truth, ["a", "a", "b", "c"], replicates=100)
        second = paired_group_bootstrap(baseline, challenger, truth, ["a", "a", "b", "c"], replicates=100)
        self.assertEqual(first, second)
        self.assertEqual(first["cluster_count"], 3)

    def test_promotion_requires_every_gate(self):
        protocol = {
            "selection_policy": {
                "promotion_gates": {
                    "source_mean_macro_f1_delta_minimum": 0.01,
                    "worst_source_macro_f1_delta_minimum": 0.0,
                    "pooled_macro_f1_delta_minimum": -0.005,
                    "maximum_single_source_macro_f1_decline": 0.02,
                    "source_predictability_macro_f1_delta_maximum": 0.02,
                    "within_source_label_shuffle_macro_f1_delta_maximum": 0.02,
                    "paired_group_bootstrap_macro_f1_delta_ci_lower_minimum": 0.0,
                }
            }
        }
        baseline = {
            "validation": {"macro_f1": 0.70},
            "validation_source_summary": {
                "unweighted_mean_macro_f1_across_sources": 0.70,
                "worst_source_macro_f1": 0.50,
            },
            "validation_by_source_dataset": {"a": {"macro_f1": 0.7}},
        }
        challenger = {
            "validation": {"macro_f1": 0.72},
            "validation_source_summary": {
                "unweighted_mean_macro_f1_across_sources": 0.72,
                "worst_source_macro_f1": 0.51,
            },
            "validation_by_source_dataset": {"a": {"macro_f1": 0.72}},
        }
        diagnostics = {
            BASELINE_ID: {
                "source_predictability": {"validation_macro_f1": 0.50},
                "within_source_label_shuffle": {"validation_macro_f1": 0.50},
            },
            CHALLENGER_ID: {
                "source_predictability": {"validation_macro_f1": 0.51},
                "within_source_label_shuffle": {"validation_macro_f1": 0.51},
            },
            "paired_group_bootstrap": {"difference_percentile_95_ci": [0.001, 0.04]},
        }
        self.assertTrue(promotion_decision(protocol, baseline, challenger, diagnostics)["all_gates_passed"])
        diagnostics[CHALLENGER_ID]["source_predictability"]["validation_macro_f1"] = 0.55
        self.assertFalse(promotion_decision(protocol, baseline, challenger, diagnostics)["all_gates_passed"])

    def test_output_paths_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepare_output_paths(root)
            (root / "text_challenger_v2_validation_selection.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                prepare_output_paths(root)


if __name__ == "__main__":
    unittest.main()
