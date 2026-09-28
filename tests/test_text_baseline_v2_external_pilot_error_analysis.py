import tempfile
import unittest
from pathlib import Path

from scripts.analyze_text_baseline_v2_external_pilot_errors import (
    branch_label_confounding,
    feature_driver_summary,
    prepare_output_paths,
)


class TextBaselineV2ExternalPilotErrorAnalysisTests(unittest.TestCase):
    def test_branch_label_confounding_detects_pure_sources(self):
        records = [
            {"ground_truth_status": "CONFIRMED", "artifact": {"source_id": "archive"}},
            {"ground_truth_status": "LEGITIMATE", "artifact": {"source_id": "sec"}},
        ]
        result = branch_label_confounding(records)
        self.assertTrue(result["class_and_collection_branch_are_perfectly_confounded"])

    def test_mixed_source_is_not_perfectly_confounded(self):
        records = [
            {"ground_truth_status": "CONFIRMED", "artifact": {"source_id": "same"}},
            {"ground_truth_status": "LEGITIMATE", "artifact": {"source_id": "same"}},
        ]
        result = branch_label_confounding(records)
        self.assertFalse(result["class_and_collection_branch_are_perfectly_confounded"])

    def test_feature_driver_summary_counts_top_contributions(self):
        items = [
            {"feature_contributions": {"toward_label_1": [{"feature": "invest", "logit_contribution": 0.2}]}},
            {"feature_contributions": {"toward_label_1": [{"feature": "invest", "logit_contribution": 0.3}]}},
        ]
        result = feature_driver_summary(items, "toward_label_1")
        self.assertEqual(result[0]["top_contribution_row_count"], 2)
        self.assertAlmostEqual(result[0]["summed_logit_contribution"], 0.5)

    def test_output_paths_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepare_output_paths(root)
            (root / "external_pilot_error_analysis_v1.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                prepare_output_paths(root)


if __name__ == "__main__":
    unittest.main()

