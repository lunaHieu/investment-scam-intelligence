import csv
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from analyze_mendeley_metadata_ablation import (
    ALL_METADATA_COLUMNS,
    PROHIBITED_PREDICTIVE_FIELDS,
    VARIANTS,
    MetadataTransformer,
    paired_comparison,
    read_rows,
    source_from_missingness_diagnostic,
)


class MendeleyMetadataAblationTests(unittest.TestCase):
    def test_metadata_transformer_preserves_missingness_only_when_requested(self):
        train = [
            {"followers": "0", "follower_following_ratio": "1.0"},
            {"followers": "99", "follower_following_ratio": ""},
        ]
        evaluation = [{"followers": "", "follower_following_ratio": ""}]

        values_only = MetadataTransformer(
            ("followers", "follower_following_ratio"), add_missingness=False
        )
        self.assertEqual(values_only.fit_transform(train).shape, (2, 2))
        self.assertEqual(values_only.transform(evaluation).shape, (1, 2))

        with_missingness = MetadataTransformer(
            ("followers", "follower_following_ratio"), add_missingness=True
        )
        self.assertEqual(with_missingness.fit_transform(train).shape, (2, 4))
        transformed = with_missingness.transform(evaluation).toarray()
        np.testing.assert_array_equal(transformed[0, 2:], np.asarray([1.0, 1.0]))

    def test_no_variant_uses_prohibited_field_as_metadata(self):
        self.assertFalse(set(ALL_METADATA_COLUMNS) & PROHIBITED_PREDICTIVE_FIELDS)
        self.assertTrue(all(variant.use_text or variant.metadata_space for variant in VARIANTS))

    def test_missingness_source_diagnostic_is_separate_and_detects_pattern(self):
        def row(source, followers, has_url):
            result = {column: "0" for column in ALL_METADATA_COLUMNS}
            result.update({
                "source_dataset": source,
                "followers": followers,
                "has_url": has_url,
            })
            return result

        train = [
            row("source_a", "", ""),
            row("source_a", "", ""),
            row("source_b", "1", "1"),
            row("source_b", "1", "1"),
        ]
        evaluation = [row("source_a", "", ""), row("source_b", "1", "1")]
        diagnostic = source_from_missingness_diagnostic(train, evaluation)
        self.assertEqual(diagnostic["missingness_signature_predictor"]["accuracy"], 1.0)
        self.assertEqual(diagnostic["unknown_signature_count"], 0)

    def test_paired_comparison_counts_fixed_and_regressed_rows(self):
        truth = np.asarray([0, 0, 1, 1])
        reference = np.asarray([1, 0, 0, 1])
        candidate = np.asarray([0, 1, 0, 1])
        result = paired_comparison(reference, candidate, truth)
        self.assertEqual(result["reference_errors_fixed"], 1)
        self.assertEqual(result["reference_correct_regressed"], 1)
        self.assertEqual(result["net_errors_removed"], 0)
        self.assertEqual(result["mcnemar_exact_two_sided_p_value"], 1.0)

    def test_read_rows_rejects_group_crossing_partitions(self):
        fieldnames = [
            "record_id",
            "source_dataset",
            "text_content",
            "label",
            "partition",
            "split_group_id",
            *ALL_METADATA_COLUMNS,
        ]
        with TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temp_dir:
            path = Path(temp_dir) / "split.csv"
            rows = []
            for index, partition in enumerate(("train", "validation", "test")):
                row = {field: "0" for field in fieldnames}
                row.update({
                    "record_id": f"row_{index}",
                    "source_dataset": "source_a",
                    "text_content": "investment message",
                    "label": str(index % 2),
                    "partition": partition,
                    "split_group_id": "shared" if index < 2 else "separate",
                })
                rows.append(row)
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "crosses partitions"):
                read_rows(path)


if __name__ == "__main__":
    unittest.main()
