import csv
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from evaluate_mendeley_text_baseline_v2 import prepare_output_paths
from mendeley_text_baseline_v2_common import (
    CANDIDATES,
    EXPECTED_SPLIT_SHA256,
    MODEL_ID,
    SELECTION_ID,
    binary_metrics,
    candidate_score,
    compute_selection_digest,
    read_final_data,
    read_selection_data,
    validate_frozen_selection,
)


FIELDS = [
    "record_id",
    "source_dataset",
    "text_content",
    "label",
    "partition",
    "split_group_id",
    "benchmark_eligible",
    "split_exclusion_reason",
]


def make_row(record_id, partition, label="0", source="phishing", group=None):
    eligible = partition in {"train", "validation", "test"}
    return {
        "record_id": record_id,
        "source_dataset": source,
        "text_content": f"text for {record_id}",
        "label": label,
        "partition": partition,
        "split_group_id": group or f"group_{record_id}",
        "benchmark_eligible": "1" if eligible else "0",
        "split_exclusion_reason": "" if eligible else f"excluded_{partition}",
    }


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


class MendeleyTextBaselineV2Tests(unittest.TestCase):
    def sample_rows(self, test_label="1"):
        return [
            make_row("train_0", "train", "0", "phishing"),
            make_row("train_1", "train", "1", "spam_email"),
            make_row("val_0", "validation", "0", "phishing"),
            make_row("val_1", "validation", "1", "spam_email"),
            make_row("test_0", "test", test_label, "phishing"),
            make_row("test_1", "test", test_label, "spam_email"),
            make_row(
                "aux_0",
                "auxiliary",
                "1",
                "fake_profile_post",
            ),
            make_row("quarantine_0", "quarantine", "0", "phishing"),
        ]

    def expected_counts(self):
        return {
            "train": 2,
            "validation": 2,
            "test": 2,
            "auxiliary": 1,
            "quarantine": 1,
        }

    def test_selection_reader_loads_only_train_and_validation(self):
        with TemporaryDirectory(dir=ROOT) as temp_dir:
            path = Path(temp_dir) / "split.csv"
            write_csv(path, self.sample_rows(test_label="SECRET"))
            splits, access = read_selection_data(
                path,
                require_frozen_hash=False,
                expected_counts=self.expected_counts(),
            )
            self.assertEqual(set(splits), {"train", "validation"})
            self.assertEqual(len(splits["train"]), 2)
            self.assertEqual(len(splits["validation"]), 2)
            self.assertEqual(access["loaded_text_rows"]["test"], 0)
            self.assertEqual(access["test_labels_used"], 0)
            self.assertEqual(access["excluded_rows_used"], 0)

    def test_final_reader_rejects_invalid_test_label(self):
        with TemporaryDirectory(dir=ROOT) as temp_dir:
            path = Path(temp_dir) / "split.csv"
            write_csv(path, self.sample_rows(test_label="SECRET"))
            with self.assertRaisesRegex(ValueError, "Benchmark label invalid"):
                read_final_data(
                    path,
                    require_frozen_hash=False,
                    expected_counts=self.expected_counts(),
                )

    def test_auxiliary_cannot_be_marked_benchmark_eligible(self):
        rows = self.sample_rows()
        rows[-2]["benchmark_eligible"] = "1"
        with TemporaryDirectory(dir=ROOT) as temp_dir:
            path = Path(temp_dir) / "split.csv"
            write_csv(path, rows)
            with self.assertRaisesRegex(ValueError, "Excluded routing fields invalid"):
                read_selection_data(
                    path,
                    require_frozen_hash=False,
                    expected_counts=self.expected_counts(),
                )

    def test_candidate_score_prioritizes_source_mean_then_worst_source(self):
        better_mean = {
            "validation_source_summary": {
                "unweighted_mean_macro_f1_across_sources": 0.80,
                "worst_source_macro_f1": 0.40,
            },
            "validation": {"macro_f1": 0.70, "balanced_accuracy": 0.70},
        }
        better_pooled = {
            "validation_source_summary": {
                "unweighted_mean_macro_f1_across_sources": 0.79,
                "worst_source_macro_f1": 0.70,
            },
            "validation": {"macro_f1": 0.95, "balanced_accuracy": 0.95},
        }
        self.assertGreater(
            candidate_score(better_mean, 1), candidate_score(better_pooled, 0)
        )

    def test_binary_metrics_include_both_labels_and_macro_f1(self):
        truth = np.asarray([0, 0, 1, 1])
        predictions = np.asarray([0, 1, 1, 1])
        probabilities = np.asarray([0.1, 0.7, 0.8, 0.9])
        result = binary_metrics(truth, predictions, probabilities)
        self.assertEqual(result["confusion_matrix"], {"tn": 1, "fp": 1, "fn": 0, "tp": 2})
        self.assertAlmostEqual(result["macro_f1"], 0.733333, places=6)
        self.assertEqual(result["per_label"]["0"]["support"], 2)
        self.assertEqual(result["per_label"]["1"]["support"], 2)

    def test_selection_digest_detects_tampering(self):
        selected = dict(CANDIDATES[0])
        selection = {
            "selection_id": SELECTION_ID,
            "model_id": MODEL_ID,
            "status": "FROZEN_VALIDATION_SELECTION_TEST_UNOPENED",
            "data": {"input_split_sha256": EXPECTED_SPLIT_SHA256},
            "data_access": {
                "test_text_transformed": 0,
                "test_labels_used": 0,
                "excluded_rows_used": 0,
            },
            "selected_hyperparameters": selected,
            "selection_digest": compute_selection_digest(selected),
        }
        with TemporaryDirectory(dir=ROOT) as temp_dir:
            path = Path(temp_dir) / "selection.json"
            path.write_text(json.dumps(selection), encoding="utf-8")
            validate_frozen_selection(selection, path)
            selection["selected_hyperparameters"] = dict(CANDIDATES[-1])
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                validate_frozen_selection(selection, path)

    def test_output_paths_refuse_overwrite(self):
        with TemporaryDirectory(dir=ROOT) as temp_dir:
            folder = Path(temp_dir)
            first = prepare_output_paths(folder, overwrite=False)
            first["model"].write_bytes(b"existing")
            with self.assertRaises(FileExistsError):
                prepare_output_paths(folder, overwrite=False)


if __name__ == "__main__":
    unittest.main()
