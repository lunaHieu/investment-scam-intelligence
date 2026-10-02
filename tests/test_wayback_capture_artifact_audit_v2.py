import unittest

from scripts.audit_and_select_usable_wayback_captures_v2 import select_balanced_usable


class WaybackCaptureArtifactAuditV2Tests(unittest.TestCase):
    def test_only_hash_verified_rows_are_balanced(self):
        capture_rows = [
            {"candidate_id": "C1", "reference_branch": "CONFIRMED_CANDIDATE", "sha256": "a"},
            {"candidate_id": "C2", "reference_branch": "CONFIRMED_CANDIDATE", "sha256": "b"},
            {"candidate_id": "L1", "reference_branch": "LEGITIMATE_CANDIDATE", "sha256": "c"},
            {"candidate_id": "L2", "reference_branch": "LEGITIMATE_CANDIDATE", "sha256": "d"},
        ]
        audit_rows = [
            {"candidate_id": "C1", "audit_state": "HASH_VERIFIED_READABLE"},
            {"candidate_id": "C2", "audit_state": "HASH_MISMATCH"},
            {"candidate_id": "L1", "audit_state": "HASH_VERIFIED_READABLE"},
            {"candidate_id": "L2", "audit_state": "HASH_VERIFIED_READABLE"},
        ]
        selected = select_balanced_usable(
            capture_rows, audit_rows, per_branch=1, seed="seed"
        )
        self.assertEqual(len(selected), 2)
        self.assertEqual({row["candidate_id"] for row in selected} & {"C2"}, set())

    def test_insufficient_usable_branch_is_rejected(self):
        with self.assertRaises(ValueError):
            select_balanced_usable([], [], per_branch=1, seed="seed")


if __name__ == "__main__":
    unittest.main()
