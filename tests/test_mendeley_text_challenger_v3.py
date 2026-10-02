import tempfile
import unittest
from pathlib import Path

from scripts.select_mendeley_text_challenger_v3 import (
    assign_development_folds,
    gate_comparison,
    make_stopword_vectorizer,
    prepare_output_paths,
)


class MendeleyTextChallengerV3Tests(unittest.TestCase):
    def test_grouped_fold_assignment_is_deterministic_and_stratified(self):
        rows = []
        for source in ("a", "b"):
            for label in ("0", "1"):
                for index in range(8):
                    group = f"{source}-{label}-{index}"
                    rows.append({"split_group_id": group, "source_dataset": source, "label": label})
                    if index == 0:
                        rows.append({"split_group_id": group, "source_dataset": source, "label": label})
        first = assign_development_folds(rows, fold_count=4, seed="fixed")
        second = assign_development_folds(rows, fold_count=4, seed="fixed")
        self.assertEqual(first, second)
        self.assertEqual(len(first), 32)
        for source in ("a", "b"):
            for label in ("0", "1"):
                observed = {
                    first[f"{source}-{label}-{index}"] for index in range(8)
                }
                self.assertEqual(observed, {0, 1, 2, 3})

    def test_grouped_fold_assignment_rejects_mixed_label_group(self):
        rows = [
            {"split_group_id": "g", "source_dataset": "a", "label": "0"},
            {"split_group_id": "g", "source_dataset": "a", "label": "1"},
        ]
        with self.assertRaises(ValueError):
            assign_development_folds(rows, fold_count=4, seed="fixed")

    def test_challenger_uses_standard_english_stop_words(self):
        vectorizer = make_stopword_vectorizer()
        matrix = vectorizer.fit_transform([
            "your account secure growth",
            "your account stable growth",
            "our service secure market",
        ])
        vocabulary = vectorizer.get_feature_names_out().tolist()
        self.assertGreater(matrix.shape[1], 0)
        self.assertNotIn("your", vocabulary)
        self.assertNotIn("our", vocabulary)
        self.assertIn("account", vocabulary)

    def test_gates_require_every_condition(self):
        thresholds = {
            "source_mean_macro_f1_delta_minimum": 0.005,
            "worst_source_macro_f1_delta_minimum": 0.0,
            "pooled_macro_f1_delta_minimum": -0.005,
            "maximum_single_source_macro_f1_decline": 0.01,
            "source_predictability_macro_f1_delta_maximum": 0.0,
            "within_source_label_shuffle_macro_f1_delta_maximum": 0.01,
        }
        values = {
            "source_mean_macro_f1_delta": 0.006,
            "worst_source_macro_f1_delta": 0.001,
            "pooled_macro_f1_delta": 0.0,
            "maximum_single_source_macro_f1_decline": 0.005,
            "source_predictability_macro_f1_delta": -0.01,
            "per_source_macro_f1_delta": {"a": 0.006},
        }
        decision = gate_comparison(
            values, thresholds, development=True, shuffle_delta=0.0
        )
        self.assertTrue(decision["all_gates_passed"])
        values["source_predictability_macro_f1_delta"] = 0.01
        decision = gate_comparison(
            values, thresholds, development=True, shuffle_delta=0.0
        )
        self.assertFalse(decision["all_gates_passed"])

    def test_output_paths_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepare_output_paths(root)
            (root / "text_challenger_v3_validation_selection.json").write_text(
                "{}", encoding="utf-8"
            )
            with self.assertRaises(FileExistsError):
                prepare_output_paths(root)


if __name__ == "__main__":
    unittest.main()
