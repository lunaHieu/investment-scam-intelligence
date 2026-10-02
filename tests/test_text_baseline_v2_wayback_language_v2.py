import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.evaluate_text_baseline_v2_wayback_language_v2 import prepare_output_paths


class TextBaselineV2WaybackLanguageV2Tests(unittest.TestCase):
    def test_output_paths_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepare_output_paths(root)
            (root / "wayback_language_results_v2.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                prepare_output_paths(root)

    def test_owner_acceptance_is_hash_bound_and_scoring_only(self):
        acceptance = json.loads(Path("configs/external_text_wayback_language_owner_acceptance_v2.json").read_text(encoding="utf-8"))
        benchmark = Path(acceptance["scope"]["benchmark_path"])
        self.assertEqual(hashlib.sha256(benchmark.read_bytes()).hexdigest(), acceptance["scope"]["benchmark_sha256"])
        self.assertTrue(acceptance["accepted_for_frozen_model_scoring"])
        self.assertFalse(acceptance["accepted_for_training_or_tuning"])
        self.assertTrue(acceptance["diagnostic_evaluation_only"])
        self.assertFalse(acceptance["scoring_contract"]["model_fit_allowed"])
        self.assertFalse(acceptance["scoring_contract"]["use_benchmark_for_tuning"])
        self.assertFalse(acceptance["scoring_contract"]["warning_or_registry_evidence_as_model_input_allowed"])


if __name__ == "__main__":
    unittest.main()
