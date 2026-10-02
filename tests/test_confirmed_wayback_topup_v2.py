import unittest

from scripts.build_confirmed_wayback_topup_queue_v2 import to_topup_row


class ConfirmedWaybackTopupV2Tests(unittest.TestCase):
    def test_topup_row_remains_unlabeled_and_unassigned(self):
        source = {
            "candidate_id": "SOURCE",
            "candidate_host": "example.com",
            "source_id": "iosco_i_scan",
            "source_record_id": "1",
            "entity_name_keys": ["example"],
            "official_reference": {"url": "https://regulator.invalid/warning"},
        }
        row = to_topup_row(source, 1, "20261001")
        self.assertEqual(row["reference_branch"], "CONFIRMED_CANDIDATE")
        self.assertFalse(row["reference_branch_is_ground_truth"])
        self.assertFalse(row["label_created"])
        self.assertEqual(row["training_eligible"], "NO")
        self.assertEqual(row["language_stratum"], "UNASSIGNED_BEFORE_TEXT_EXTRACTION")


if __name__ == "__main__":
    unittest.main()
