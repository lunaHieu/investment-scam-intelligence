import unittest

from scripts.build_external_text_wayback_language_queue_v2 import (
    normalized_host,
    to_acquisition_row,
)


class ExternalTextWaybackLanguageExpansionV2Tests(unittest.TestCase):
    def test_normalized_host_removes_only_leading_www(self):
        self.assertEqual(normalized_host("WWW.Example.COM."), "example.com")
        self.assertEqual(normalized_host("notwww.example.com"), "notwww.example.com")

    def test_acquisition_row_is_unlabeled_and_language_unassigned(self):
        source = {
            "candidate_id": "SOURCE_1",
            "candidate_host": "example.com",
            "source_id": "sec_iapd",
            "source_record_id": "123",
            "entity_name_keys": ["example"],
            "official_reference": {"url": "https://example.invalid/reference"},
        }
        row = to_acquisition_row(
            source,
            branch="LEGITIMATE_CANDIDATE",
            rank=1,
            target_timestamp="20260930",
        )
        self.assertFalse(row["reference_branch_is_ground_truth"])
        self.assertFalse(row["label_created"])
        self.assertEqual(row["training_eligible"], "NO")
        self.assertEqual(row["language_stratum"], "UNASSIGNED_BEFORE_TEXT_EXTRACTION")
        self.assertEqual(row["archive_acquisition_state"], "NEEDS_ARCHIVE_QUERY")


if __name__ == "__main__":
    unittest.main()
