import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from analyze_mendeley_text_baseline_v2_errors import (
    calibration_summary,
    confidence_band,
    redact_excerpt,
    select_review_queue,
    top_row_contributions,
)


class MendeleyTextBaselineV2ErrorAnalysisTests(unittest.TestCase):
    def test_confidence_band_boundaries_are_fixed(self):
        self.assertEqual(confidence_band(0.5), "0.50-0.60")
        self.assertEqual(confidence_band(0.6), "0.60-0.75")
        self.assertEqual(confidence_band(0.75), "0.75-0.90")
        self.assertEqual(confidence_band(0.9), "0.90-0.99")
        self.assertEqual(confidence_band(0.99), "0.99-1.00")
        self.assertEqual(confidence_band(1.0), "0.99-1.00")

    def test_calibration_uses_fixed_bins_and_brier_score(self):
        truth = np.asarray([0, 0, 1, 1], dtype=np.float64)
        scores = np.asarray([0.1, 0.2, 0.8, 0.9], dtype=np.float64)
        result = calibration_summary(truth, scores)
        self.assertAlmostEqual(result["brier_score"], 0.025, places=6)
        self.assertAlmostEqual(result["expected_calibration_error"], 0.15, places=6)
        self.assertEqual(sum(item["row_count"] for item in result["bins"]), 4)

    def test_feature_contributions_use_sparse_value_times_coefficient(self):
        result = top_row_contributions(
            np.asarray([0, 1, 2]),
            np.asarray([0.5, 0.25, 2.0]),
            np.asarray([2.0, -4.0, 0.1]),
            np.asarray(["positive", "negative", "small"]),
            limit=2,
        )
        self.assertEqual(
            result["toward_label_1"],
            [
                {"feature": "positive", "logit_contribution": 1.0},
                {"feature": "small", "logit_contribution": 0.2},
            ],
        )
        self.assertEqual(
            result["toward_label_0"],
            [{"feature": "negative", "logit_contribution": -1.0}],
        )

    def test_review_queue_is_stratified_and_group_unique(self):
        errors = []
        for index, (source, error_type, group, confidence) in enumerate(
            [
                ("a", "false_positive", "shared", 0.99),
                ("a", "false_positive", "g2", 0.95),
                ("a", "false_negative", "shared", 0.98),
                ("a", "false_negative", "g3", 0.90),
                ("b", "false_positive", "g4", 0.88),
            ]
        ):
            errors.append(
                {
                    "record_id": f"r{index}",
                    "split_group_id": group,
                    "source_dataset": source,
                    "source_label": 0 if error_type == "false_positive" else 1,
                    "predicted_label": 1 if error_type == "false_positive" else 0,
                    "error_type": error_type,
                    "score_label_1": 0.9,
                    "prediction_confidence": confidence,
                    "confidence_band": confidence_band(confidence),
                    "surface_token_count": 3,
                    "length_band": "0-12",
                    "unique_analyzed_term_count": 3,
                    "matched_vocabulary_term_count": 2,
                    "unique_vectorizer_term_coverage": 0.666667,
                    "nearest_fit_record_id": "fit",
                    "nearest_fit_source_dataset": "a",
                    "nearest_fit_partition": "train",
                    "nearest_fit_cosine_similarity": 0.5,
                    "feature_contributions": {},
                    "redacted_text_excerpt": "sample",
                }
            )
        queue, strata = select_review_queue(errors, per_source_error_type=2)
        groups = [item["split_group_id"] for item in queue]
        self.assertEqual(len(groups), len(set(groups)))
        self.assertEqual(len(queue), 4)
        self.assertEqual(strata["a|false_positive"]["selected_unique_groups"], 2)
        self.assertEqual(strata["a|false_negative"]["selected_unique_groups"], 1)
        self.assertTrue(all("new_label" not in item for item in queue))

    def test_excerpt_redacts_common_identifiers_and_is_bounded(self):
        value = redact_excerpt(
            "Email me at person@example.com, visit https://example.com, call +1 212 555 0199, "
            "or pay 1C6HUk3DXbhdgB4m5T5brQLJyZPDxNtoMB."
        )
        self.assertIn("[EMAIL]", value)
        self.assertIn("[URL]", value)
        self.assertIn("[PHONE]", value)
        self.assertIn("[LONG_ID]", value)
        self.assertLessEqual(len(value), 240)


if __name__ == "__main__":
    unittest.main()
