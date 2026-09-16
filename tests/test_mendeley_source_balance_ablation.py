import sys
import unittest
from pathlib import Path

import numpy as np


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from analyze_mendeley_source_balance_ablation import (
    STRATEGIES,
    compute_sample_weights,
    selection_score,
    source_summary,
    weight_profile,
)


class MendeleySourceBalanceAblationTests(unittest.TestCase):
    def rows(self):
        return [
            {"source_dataset": "large", "label": "0"},
            {"source_dataset": "large", "label": "0"},
            {"source_dataset": "large", "label": "1"},
            {"source_dataset": "large", "label": "1"},
            {"source_dataset": "small", "label": "0"},
            {"source_dataset": "small", "label": "1"},
        ]

    def test_all_weight_strategies_are_positive_finite_and_mean_one(self):
        for strategy in STRATEGIES:
            weights = compute_sample_weights(self.rows(), strategy)
            self.assertTrue(np.all(np.isfinite(weights)))
            self.assertTrue(np.all(weights > 0))
            self.assertAlmostEqual(float(np.mean(weights)), 1.0)

    def test_inverse_source_frequency_equalizes_total_source_weight(self):
        rows = self.rows()
        weights = compute_sample_weights(rows, "inverse_source_frequency")
        profile = weight_profile(rows, weights)
        totals = list(profile["total_weight_by_source_dataset"].values())
        self.assertAlmostEqual(totals[0], totals[1])

    def test_inverse_source_label_frequency_equalizes_observed_cells(self):
        rows = self.rows()
        weights = compute_sample_weights(rows, "inverse_source_label_frequency")
        profile = weight_profile(rows, weights)
        totals = list(profile["total_weight_by_source_and_label"].values())
        self.assertTrue(all(abs(value - totals[0]) < 1e-9 for value in totals))

    def test_unweighted_has_full_effective_sample_size(self):
        rows = self.rows()
        profile = weight_profile(rows, compute_sample_weights(rows, "unweighted"))
        self.assertEqual(profile["effective_sample_size"], len(rows))
        self.assertEqual(profile["effective_sample_ratio"], 1.0)

    def test_source_summary_and_selection_prioritize_cross_source_mean(self):
        by_source = {
            "a": {"macro_f1": 0.8, "balanced_accuracy": 0.7},
            "b": {"macro_f1": 0.4, "balanced_accuracy": 0.5},
        }
        summary = source_summary(by_source)
        self.assertEqual(summary["unweighted_mean_macro_f1_across_sources"], 0.6)
        self.assertEqual(summary["worst_source_macro_f1"], 0.4)
        report = {
            "validation_source_summary": summary,
            "validation": {"macro_f1": 0.9, "f1_label_1": 0.9},
        }
        score = selection_score("unweighted", report)
        self.assertEqual(score[0], 0.6)
        self.assertEqual(score[1], 0.4)

    def test_unknown_weight_strategy_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown weighting strategy"):
            compute_sample_weights(self.rows(), "unknown")


if __name__ == "__main__":
    unittest.main()
