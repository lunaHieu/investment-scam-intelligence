import tempfile
import unittest
from pathlib import Path

from scripts.analyze_text_baseline_v2_wayback_language_v2_errors import (
    feature_driver_summary,
    matched_strata_summary,
    prepare_output_paths,
)


class TextBaselineV2WaybackLanguageV2ErrorAnalysisTests(unittest.TestCase):
    def test_both_labels_share_capture_and_language_strata(self):
        records = [
            {"ground_truth_status": "CONFIRMED", "capture_stratum": "WAYBACK", "language_stratum": "ENGLISH", "evidence": {"official_reference_record": {"reference_role": "WARNING"}}},
            {"ground_truth_status": "LEGITIMATE", "capture_stratum": "WAYBACK", "language_stratum": "ENGLISH", "evidence": {"official_reference_record": {"reference_role": "REGISTRATION"}}},
        ]
        self.assertTrue(matched_strata_summary(records)["both_labels_share_capture_and_language_strata"])

    def test_language_mismatch_is_detected(self):
        records = [
            {"ground_truth_status": "CONFIRMED", "capture_stratum": "WAYBACK", "language_stratum": "ENGLISH", "evidence": {"official_reference_record": {}}},
            {"ground_truth_status": "LEGITIMATE", "capture_stratum": "WAYBACK", "language_stratum": "SPANISH", "evidence": {"official_reference_record": {}}},
        ]
        self.assertFalse(matched_strata_summary(records)["both_labels_share_capture_and_language_strata"])

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
            (root / "wayback_language_error_analysis_v2.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                prepare_output_paths(root)


if __name__ == "__main__":
    unittest.main()
