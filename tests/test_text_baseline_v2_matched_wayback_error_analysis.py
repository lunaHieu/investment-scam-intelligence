import tempfile
import unittest
from pathlib import Path

from scripts.analyze_text_baseline_v2_matched_wayback_errors import (
    feature_driver_summary,
    matched_capture_summary,
    prepare_output_paths,
)


class TextBaselineV2MatchedWaybackErrorAnalysisTests(unittest.TestCase):
    def test_both_labels_share_capture_stratum(self):
        records = [
            {"ground_truth_status": "CONFIRMED", "capture_stratum": "WAYBACK", "evidence": []},
            {"ground_truth_status": "LEGITIMATE", "capture_stratum": "WAYBACK", "evidence": []},
        ]
        self.assertTrue(matched_capture_summary(records)["both_labels_share_one_capture_stratum"])

    def test_different_capture_strata_are_detected(self):
        records = [
            {"ground_truth_status": "CONFIRMED", "capture_stratum": "WAYBACK", "evidence": []},
            {"ground_truth_status": "LEGITIMATE", "capture_stratum": "LIVE", "evidence": []},
        ]
        self.assertFalse(matched_capture_summary(records)["both_labels_share_one_capture_stratum"])

    def test_feature_driver_summary_counts_rows(self):
        items = [
            {"feature_contributions": {"toward_label_1": [{"feature": "profit", "logit_contribution": 0.2}]}},
            {"feature_contributions": {"toward_label_1": [{"feature": "profit", "logit_contribution": 0.4}]}},
        ]
        result = feature_driver_summary(items, "toward_label_1")
        self.assertEqual(result[0]["feature"], "profit")
        self.assertEqual(result[0]["top_contribution_row_count"], 2)
        self.assertAlmostEqual(result[0]["summed_logit_contribution"], 0.6)

    def test_output_paths_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepare_output_paths(root)
            (root / "matched_wayback_error_analysis_v1.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                prepare_output_paths(root)


if __name__ == "__main__":
    unittest.main()
