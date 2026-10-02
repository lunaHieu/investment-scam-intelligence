import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "analyze_mendeley_text_challenger_v4_oof_errors.py"
PROTOCOL_PATH = REPO_ROOT / "configs" / "mendeley_text_challenger_v4_oof_error_analysis_protocol.json"
SPEC = importlib.util.spec_from_file_location("semantic_v4_oof_errors", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class SemanticChallengerV4OOFErrorAnalysisTests(unittest.TestCase):
    def test_protocol_is_frozen_and_all_inputs_match(self):
        protocol = MODULE.validate_protocol(PROTOCOL_PATH)
        self.assertEqual(protocol["scope"]["partition"], "train")
        self.assertFalse(protocol["scope"]["model_fit_allowed"])
        self.assertFalse(protocol["scope"]["new_embedding_computation_allowed"])

    def test_transition_definitions_cover_all_correctness_states(self):
        self.assertEqual(MODULE.transition(1, 1, 1), "both_correct")
        self.assertEqual(MODULE.transition(1, 1, 0), "e5_regression")
        self.assertEqual(MODULE.transition(1, 0, 1), "e5_recovery")
        self.assertEqual(MODULE.transition(1, 0, 0), "both_wrong")

    def test_token_buckets_have_fixed_boundaries(self):
        self.assertEqual(MODULE.token_bucket(32), "le_32")
        self.assertEqual(MODULE.token_bucket(33), "33_128")
        self.assertEqual(MODULE.token_bucket(128), "33_128")
        self.assertEqual(MODULE.token_bucket(129), "129_512")
        self.assertEqual(MODULE.token_bucket(512), "129_512")
        self.assertEqual(MODULE.token_bucket(513), "gt_512")

    def test_rate_summary_counts_regressions_and_recoveries(self):
        records = [
            {"transition": "both_correct"},
            {"transition": "e5_regression"},
            {"transition": "e5_regression"},
            {"transition": "e5_recovery"},
            {"transition": "both_wrong"},
        ]
        summary = MODULE.rate_summary(records)
        self.assertEqual(summary["baseline_error_count"], 2)
        self.assertEqual(summary["challenger_error_count"], 3)
        self.assertEqual(summary["net_e5_regression_rate"], 0.2)

    def test_nearest_neighbor_excludes_self_and_same_group(self):
        embeddings = np.zeros((4, 384), dtype=np.float32)
        embeddings[:, 0] = 1.0
        rows = [
            {"record_id": f"r{index:04d}", "split_group_id": f"g{index:04d}"}
            for index in range(4)
        ]
        rows[1]["split_group_id"] = rows[0]["split_group_id"]
        indices, similarities = MODULE.nearest_neighbors(embeddings, rows, block_rows=256)
        self.assertNotIn(indices[0], {0, 1})
        self.assertNotIn(indices[1], {0, 1})
        self.assertTrue(np.allclose(similarities, 1.0))

    def test_redaction_and_bounded_excerpt(self):
        text = "Email person@example.com phone +1 (555) 123-4567 at https://example.com/ " + "x" * 300
        excerpt = MODULE.redact_excerpt(text, limit=80)
        self.assertLessEqual(len(excerpt), 80)
        self.assertIn("[EMAIL]", excerpt)
        self.assertIn("[PHONE]", excerpt)
        self.assertIn("[URL]", excerpt)

    def test_output_paths_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = MODULE.prepare_outputs(root)
            paths["report"].touch()
            with self.assertRaises(FileExistsError):
                MODULE.prepare_outputs(root)


if __name__ == "__main__":
    unittest.main()
