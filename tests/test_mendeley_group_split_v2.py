import csv
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_mendeley_group_split_v2 import (
    AUXILIARY_REASON,
    QUARANTINE_REASON,
    assign_groups,
    build_groups,
    classify_groups,
    materialize_rows,
    parse_fake_entity,
    validate_raw_contract,
    write_json,
)


def row(record_id, text, label="0", source="phishing", partition="train"):
    return {
        "record_id": record_id,
        "source_dataset": source,
        "text_content": text,
        "label": label,
        "partition": partition,
        "has_metadata": "False",
    }


def letters(index):
    return chr(97 + (index // 26) % 26) + chr(97 + index % 26)


class MendeleyGroupSplitV2Tests(unittest.TestCase):
    def test_four_rule_union_is_transitive_and_blanks_stay_separate(self):
        rows = [
            row("a", "Call 123 now!"),
            row("b", "Call 123 now"),
            row("c", "Call 999 now"),
            row("blank_a", ""),
            row("blank_b", ""),
        ]
        groups = build_groups(rows)
        membership = [set(rows[index]["record_id"] for index in group) for group in groups]
        self.assertIn({"a", "b", "c"}, membership)
        self.assertIn({"blank_a"}, membership)
        self.assertIn({"blank_b"}, membership)

    def test_short_digit_url_and_placeholder_variants_group(self):
        rows = [
            row("left", "DM @alice: invest 25 at https://example.test [PHONE]"),
            row("right", "DM @bob: invest 500 at https://other.test [phone]"),
        ]
        self.assertEqual(len(build_groups(rows)), 1)

    def test_conflicting_component_is_quarantined_without_relabeling(self):
        rows = [
            row("bad_1", "same offer 25 now", label="1"),
            row("bad_2", "same offer 99 now", label="0"),
            row("safe", "independent message alpha", label="0"),
        ]
        groups = build_groups(rows)
        eligible, fixed, reasons = classify_groups(rows, groups)
        assigned = assign_groups(rows, eligible)
        output = materialize_rows(rows, groups, assigned, fixed, reasons)
        selected = {item["record_id"]: item for item in output}
        self.assertEqual(selected["bad_1"]["partition"], "quarantine")
        self.assertEqual(selected["bad_2"]["partition"], "quarantine")
        self.assertEqual(selected["bad_1"]["label"], "1")
        self.assertEqual(selected["bad_2"]["label"], "0")
        self.assertEqual(
            selected["bad_1"]["split_exclusion_reason"], QUARANTINE_REASON
        )

    def test_fake_profile_is_auxiliary_even_if_labels_conflict(self):
        entity = "123e4567-e89b-42d3-a456-426614174000"
        rows = [
            row(
                f"fake_profile_post_{entity}_0",
                "same fake text",
                label="0",
                source="fake_profile_post",
            ),
            row(
                f"fake_profile_post_{entity}_1",
                "same fake text",
                label="1",
                source="fake_profile_post",
            ),
        ]
        groups = build_groups(rows)
        eligible, fixed, reasons = classify_groups(rows, groups)
        self.assertEqual(eligible, [])
        self.assertEqual(set(fixed.values()), {"auxiliary"})
        self.assertEqual(set(reasons.values()), {AUXILIARY_REASON})

    def test_fake_entity_parser_is_strict(self):
        valid = "fake_profile_post_123e4567-e89b-42d3-a456-426614174000_58"
        self.assertEqual(
            parse_fake_entity(valid),
            ("123e4567-e89b-42d3-a456-426614174000", 58),
        )
        self.assertIsNone(parse_fake_entity(valid + "_extra"))
        self.assertIsNone(
            parse_fake_entity("fake_profile_post_123e4567-e89b-42d3-a456-426614174000")
        )
        self.assertIsNone(
            parse_fake_entity("fake_profile_post_not-a-uuid_0")
        )

    def test_assignment_and_group_ids_are_independent_of_input_order(self):
        rows = []
        for index in range(120):
            source = "phishing" if index % 2 else "spam_email"
            label = str((index // 2) % 2)
            token = letters(index)
            rows.append(row(f"id_{index:03d}", f"unique alphabetic token {token}", label, source))

        def mapping(values):
            groups = build_groups(values)
            eligible, fixed, reasons = classify_groups(values, groups)
            assigned = assign_groups(values, eligible)
            output = materialize_rows(values, groups, assigned, fixed, reasons)
            return {
                item["record_id"]: (item["partition"], item["split_group_id"])
                for item in output
            }

        self.assertEqual(mapping(rows), mapping(list(reversed(rows))))

    def test_materialization_preserves_source_values_and_order(self):
        rows = [
            row("first", "unique alpha", label="0", partition="test"),
            row("second", "unique beta", label="1", partition="validation"),
        ]
        groups = build_groups(rows)
        eligible, fixed, reasons = classify_groups(rows, groups)
        assigned = assign_groups(rows, eligible)
        output = materialize_rows(rows, groups, assigned, fixed, reasons)
        self.assertEqual([item["record_id"] for item in output], ["first", "second"])
        self.assertEqual(output[0]["original_partition"], "test")
        self.assertEqual(output[1]["original_partition"], "validation")
        self.assertEqual(output[0]["label"], rows[0]["label"])
        self.assertEqual(output[1]["text_content"], rows[1]["text_content"])
        self.assertEqual(output[0]["benchmark_eligible"], "1")

    def test_derived_input_and_overwrite_are_rejected(self):
        with TemporaryDirectory(dir=ROOT) as temp_dir:
            folder = Path(temp_dir)
            derived = folder / "derived.csv"
            with derived.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "record_id",
                        "source_dataset",
                        "text_content",
                        "label",
                        "partition",
                        "original_partition",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "record_id": "one",
                        "source_dataset": "phishing",
                        "text_content": "text",
                        "label": "0",
                        "partition": "train",
                        "original_partition": "test",
                    }
                )
            with derived.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                fieldnames = list(reader.fieldnames or [])
                rows = list(reader)
            with self.assertRaisesRegex(ValueError, "derived split fields"):
                validate_raw_contract(
                    derived, fieldnames, rows, require_pinned_hash=False
                )

            report = folder / "report.json"
            report.write_text("{}\n", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                write_json(report, {"new": True}, overwrite=False)


if __name__ == "__main__":
    unittest.main()
