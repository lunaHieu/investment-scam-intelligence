import importlib.util
import tempfile
import unittest
from collections import Counter
from pathlib import Path

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = REPO_ROOT / "scripts" / "generate_mendeley_text_challenger_v4_embeddings.py"
DEVELOPMENT_PATH = REPO_ROOT / "scripts" / "run_mendeley_text_challenger_v4_development.py"
PROTOCOL_PATH = REPO_ROOT / "configs" / "mendeley_text_challenger_v4_protocol.json"
SPLIT_PATH = Path(
    r"D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026"
    r"\group_split_v2\mendeley_v2_group_split_v2.csv"
)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


GENERATOR = load_module("semantic_v4_generator", GENERATOR_PATH)
DEVELOPMENT = load_module("semantic_v4_development", DEVELOPMENT_PATH)


class SemanticChallengerV4DevelopmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = GENERATOR.validate_protocol(PROTOCOL_PATH, SPLIT_PATH)
        cls.rows, cls.access = GENERATOR.read_train_only(SPLIT_PATH)

    def test_train_only_reader_retains_exact_scope(self):
        self.assertEqual(len(self.rows), 3916)
        self.assertEqual(len({row["split_group_id"] for row in self.rows}), 3783)
        self.assertTrue(all(row["partition"] == "train" for row in self.rows))
        self.assertEqual(self.access["validation_text_rows_retained"], 0)
        self.assertEqual(self.access["validation_labels_accessed"], 0)
        self.assertEqual(self.access["test_text_rows_retained"], 0)
        self.assertEqual(self.access["test_labels_accessed"], 0)

    def test_ordered_input_digest_changes_with_order_or_text(self):
        rows = [
            {"record_id": "a", "text_content": "one"},
            {"record_id": "b", "text_content": "two"},
        ]
        original = GENERATOR.ordered_input_digest(rows, "query: ")
        self.assertEqual(original, GENERATOR.ordered_input_digest(rows, "query: "))
        self.assertNotEqual(original, GENERATOR.ordered_input_digest(list(reversed(rows)), "query: "))
        changed = [dict(row) for row in rows]
        changed[1]["text_content"] = "different"
        self.assertNotEqual(original, GENERATOR.ordered_input_digest(changed, "query: "))

    def test_fold_assignment_is_deterministic_grouped_and_stratified(self):
        first = DEVELOPMENT.assign_development_folds(
            self.rows, fold_count=4, seed="MENDELEY_TEXT_CHALLENGER_V4_20261002"
        )
        second = DEVELOPMENT.assign_development_folds(
            list(reversed(self.rows)),
            fold_count=4,
            seed="MENDELEY_TEXT_CHALLENGER_V4_20261002",
        )
        self.assertEqual(first, second)
        self.assertEqual(len(first), 3783)
        for source in sorted({row["source_dataset"] for row in self.rows}):
            for label in ("0", "1"):
                folds = {
                    first[row["split_group_id"]]
                    for row in self.rows
                    if row["source_dataset"] == source and row["label"] == label
                }
                self.assertEqual(folds, {0, 1, 2, 3})

    def test_shuffle_preserves_each_source_label_count(self):
        shuffled = DEVELOPMENT.shuffled_labels_within_source(self.rows, seed=20261002)
        before = Counter(
            (row["source_dataset"], int(row["label"])) for row in self.rows
        )
        after = Counter(
            (row["source_dataset"], int(value))
            for row, value in zip(self.rows, shuffled)
        )
        self.assertEqual(before, after)
        self.assertFalse(np.array_equal(shuffled, np.asarray([int(row["label"]) for row in self.rows])))

    def test_development_gate_requires_every_condition(self):
        thresholds = self.protocol["selection_policy"]["development_oof_gates"]
        passing = {
            "source_mean_macro_f1_delta": 0.005,
            "worst_source_macro_f1_delta": 0.0,
            "pooled_macro_f1_delta": -0.005,
            "maximum_single_source_macro_f1_decline": 0.01,
            "source_predictability_macro_f1_delta": 0.0,
            "per_source_macro_f1_delta": {},
        }
        self.assertTrue(DEVELOPMENT.development_gate(passing, thresholds, 0.01)["all_gates_passed"])
        failing = dict(passing)
        failing["source_predictability_macro_f1_delta"] = 0.000001
        decision = DEVELOPMENT.development_gate(failing, thresholds, 0.01)
        self.assertFalse(decision["all_gates_passed"])
        self.assertEqual(
            decision["failed_gates"],
            ["source_predictability_macro_f1_delta_maximum"],
        )

    def test_output_paths_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            embedding_path, metadata_path = GENERATOR.prepare_outputs(root)
            embedding_path.touch()
            with self.assertRaises(FileExistsError):
                GENERATOR.prepare_outputs(root)
            embedding_path.unlink()
            metadata_path.touch()
            with self.assertRaises(FileExistsError):
                GENERATOR.prepare_outputs(root)

            development_root = root / "development"
            result_path, predictions_path = DEVELOPMENT.prepare_outputs(development_root)
            result_path.touch()
            with self.assertRaises(FileExistsError):
                DEVELOPMENT.prepare_outputs(development_root)
            result_path.unlink()
            predictions_path.touch()
            with self.assertRaises(FileExistsError):
                DEVELOPMENT.prepare_outputs(development_root)


if __name__ == "__main__":
    unittest.main()
