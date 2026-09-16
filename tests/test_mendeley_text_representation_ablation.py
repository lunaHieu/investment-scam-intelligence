import sys
import unittest
from pathlib import Path

import numpy as np


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from analyze_mendeley_text_representation_ablation import (
    BASELINE_REPRESENTATION,
    CHAR_MAX_FEATURES,
    PROMOTION_ELIGIBLE_REPRESENTATIONS,
    REPRESENTATIONS,
    combine_and_normalize,
    diagnostic_normalize_template,
    macro_f1_from_confusion,
    make_character_vectorizer,
    normalized_template_partition_diagnostic,
    paired_group_bootstrap,
    representation_score,
    safe_feature_text,
    within_source_label_shuffle,
)


class MendeleyTextRepresentationAblationTests(unittest.TestCase):
    def test_expected_representations_and_baseline_are_fixed(self):
        self.assertEqual(BASELINE_REPRESENTATION, "word_1_2")
        self.assertEqual(len(REPRESENTATIONS), 4)
        self.assertIn("char_wb_3_5", REPRESENTATIONS)
        self.assertIn("char_3_5", REPRESENTATIONS)
        self.assertIn("word_1_2_plus_char_wb_3_5", REPRESENTATIONS)
        self.assertNotIn("char_3_5", PROMOTION_ELIGIBLE_REPRESENTATIONS)

    def test_character_vectorizer_contract(self):
        vectorizer = make_character_vectorizer("char_wb")
        self.assertEqual(vectorizer.analyzer, "char_wb")
        self.assertEqual(vectorizer.ngram_range, (3, 5))
        self.assertEqual(vectorizer.min_df, 2)
        self.assertEqual(vectorizer.max_features, CHAR_MAX_FEATURES)
        with self.assertRaisesRegex(ValueError, "Unsupported character analyzer"):
            make_character_vectorizer("word")

    def test_combined_matrix_is_l2_normalized(self):
        from scipy import sparse

        left = sparse.csr_matrix([[3.0, 4.0], [0.0, 2.0]])
        right = sparse.csr_matrix([[0.0, 5.0], [2.0, 0.0]])
        combined = combine_and_normalize(left, right)
        norms = np.sqrt(combined.multiply(combined).sum(axis=1)).A1
        np.testing.assert_allclose(norms, np.ones(2))

    def test_representation_score_prioritizes_cross_source_mean(self):
        report = {
            "validation": {"macro_f1": 0.9, "f1_label_1": 0.8},
            "validation_source_summary": {
                "unweighted_mean_macro_f1_across_sources": 0.7,
                "worst_source_macro_f1": 0.4,
            },
        }
        score = representation_score("char_wb_3_5", report)
        self.assertEqual(score[0], 0.7)
        self.assertEqual(score[1], 0.4)

    def test_within_source_shuffle_preserves_each_source_label_counts(self):
        rows = [
            {"source_dataset": source, "label": label}
            for source, label in (
                ("a", "0"),
                ("a", "1"),
                ("a", "1"),
                ("b", "0"),
                ("b", "0"),
                ("b", "1"),
            )
        ]
        shuffled = within_source_label_shuffle(rows)
        for source in ("a", "b"):
            indices = [
                index for index, row in enumerate(rows) if row["source_dataset"] == source
            ]
            original = sorted(int(rows[index]["label"]) for index in indices)
            result = sorted(int(shuffled[index]) for index in indices)
            self.assertEqual(result, original)

    def test_group_bootstrap_uses_clusters_and_is_deterministic(self):
        truth = np.asarray([0, 0, 1, 1, 1, 0])
        reference = np.asarray([0, 1, 0, 1, 0, 0])
        candidate = np.asarray([0, 0, 1, 1, 1, 0])
        groups = ["g1", "g1", "g2", "g2", "g3", "g4"]
        first = paired_group_bootstrap(
            reference, candidate, truth, groups, replicates=200
        )
        second = paired_group_bootstrap(
            reference, candidate, truth, groups, replicates=200
        )
        self.assertEqual(first, second)
        self.assertEqual(first["cluster_count"], 4)
        self.assertEqual(first["largest_cluster_rows"], 2)
        self.assertGreater(first["macro_f1_difference"], 0)

    def test_macro_f1_from_confusion(self):
        self.assertEqual(macro_f1_from_confusion(np.asarray([2, 0, 0, 2])), 1.0)

    def test_diagnostic_normalizer_collapses_digit_template_variants(self):
        left = "BUY 123 shares — [PHONE] https://example.test/123"
        right = "buy 987 shares — [phone] www.other.test/55"
        self.assertEqual(
            diagnostic_normalize_template(left), diagnostic_normalize_template(right)
        )

    def test_normalized_template_audit_reports_cross_partition_match(self):
        splits = {
            "train": [
                {
                    "source_dataset": "s",
                    "partition": "train",
                    "text_content": "profit 123 now",
                    "label": "1",
                }
            ],
            "validation": [
                {
                    "source_dataset": "s",
                    "partition": "validation",
                    "text_content": "PROFIT 456 NOW",
                    "label": "1",
                }
            ],
            "test": [
                {
                    "source_dataset": "s",
                    "partition": "test",
                    "text_content": "unrelated",
                    "label": "0",
                }
            ],
        }
        report = normalized_template_partition_diagnostic(splits)
        self.assertEqual(report["cross_partition_normalized_template_count"], 1)
        self.assertEqual(report["affected_row_count"], 2)
        self.assertEqual(
            report["same_source_match_to_train"]["validation"]["s"]["matching_rows"],
            1,
        )

    def test_feature_text_escapes_control_characters(self):
        self.assertEqual(safe_feature_text("a\nb\tc\\d"), "a\\nb\\tc\\\\d")


if __name__ == "__main__":
    unittest.main()
