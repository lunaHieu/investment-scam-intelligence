import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from audit_mendeley_text_overlap import normalize_surface, normalize_template
from build_mendeley_group_split import assign_groups, build_groups, cross_split_group_count


class MendeleyGroupSplitTests(unittest.TestCase):
    def make_rows(self):
        rows = []
        for index in range(40):
            label = str(index % 2)
            source = "source_a" if index % 3 else "source_b"
            text = f"Unique investment review message number {index} with enough words for template checks"
            rows.append({
                "record_id": f"row_{index}",
                "source_dataset": source,
                "text_content": text,
                "label": label,
                "partition": "train",
            })
        rows.extend([
            {
                "record_id": "duplicate_a",
                "source_dataset": "source_a",
                "text_content": "Guaranteed return offer. Contact [EMAIL] and visit [URL] for private investment access.",
                "label": "1",
                "partition": "validation",
            },
            {
                "record_id": "duplicate_b",
                "source_dataset": "source_a",
                "text_content": "GUARANTEED return offer contact person@example.test and visit https://example.test for private investment access",
                "label": "1",
                "partition": "test",
            },
        ])
        return rows

    def test_assignment_is_deterministic_and_keeps_duplicate_groups_together(self):
        rows = self.make_rows()
        groups = build_groups(rows)
        first = assign_groups(rows, groups)
        second = assign_groups(rows, groups)
        self.assertEqual(first, second)
        self.assertEqual(first[len(rows) - 2], first[len(rows) - 1])

        for index, row in enumerate(rows):
            row["partition"] = first[index]
        self.assertEqual(cross_split_group_count(rows, normalize_surface, 1), 0)
        self.assertEqual(cross_split_group_count(rows, normalize_template, 10), 0)


if __name__ == "__main__":
    unittest.main()
