import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.evaluate_text_baseline_v2_wayback_holdout_v3 import prepare_output_paths


class TextBaselineV2WaybackHoldoutV3Tests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_output_paths_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepare_output_paths(root)
            (root / "wayback_holdout_results_v3.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                prepare_output_paths(root)

    def test_owner_acceptance_is_hash_bound_and_scoring_only(self):
        acceptance = json.loads(
            (self.ROOT / "configs/external_text_wayback_holdout_owner_acceptance_v3.json").read_text(encoding="utf-8")
        )
        benchmark = Path(acceptance["scope"]["benchmark_path"])
        registry = self.ROOT / acceptance["scope"]["benchmark_registry_path"]
        self.assertEqual(hashlib.sha256(benchmark.read_bytes()).hexdigest(), acceptance["scope"]["benchmark_sha256"])
        self.assertEqual(hashlib.sha256(registry.read_bytes()).hexdigest(), acceptance["scope"]["benchmark_registry_sha256"])
        self.assertTrue(acceptance["accepted_for_frozen_model_scoring"])
        self.assertFalse(acceptance["accepted_for_training_or_tuning"])
        self.assertTrue(acceptance["diagnostic_evaluation_only"])
        self.assertFalse(acceptance["scoring_contract"]["model_fit_allowed"])
        self.assertFalse(acceptance["scoring_contract"]["use_benchmark_for_tuning"])
        self.assertFalse(acceptance["scoring_contract"]["warning_or_registry_evidence_as_model_input_allowed"])

    def test_evaluation_registry_keeps_tuning_and_deployment_closed(self):
        registry = json.loads(
            (self.ROOT / "registry/analyses/text_baseline_v2_wayback_holdout_v3.json").read_text(encoding="utf-8")
        )
        self.assertEqual(registry["metrics"]["confusion_matrix"], {"tn": 10, "fp": 5, "fn": 3, "tp": 12})
        self.assertEqual(registry["metrics"]["macro_f1"], 0.732143)
        self.assertFalse(registry["comparison_context"]["paired_significance_claimed"])
        self.assertFalse(registry["safety_contract"]["benchmark_used_for_tuning"])
        self.assertFalse(registry["safety_contract"]["training_allowed"])
        self.assertFalse(registry["safety_contract"]["deployment_allowed"])


if __name__ == "__main__":
    unittest.main()
