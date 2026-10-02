import unittest

from scripts.build_wayback_topup_balanced_capture_plan_v2 import select_topup_pair


class WaybackTopupBalancedCapturePlanV2Tests(unittest.TestCase):
    def test_pairs_all_confirmed_with_untouched_legitimate(self):
        confirmed = [
            {"candidate_id": "C1", "reference_branch": "CONFIRMED_CANDIDATE", "available": True, "snapshot_timestamp": "1", "error": None},
            {"candidate_id": "C2", "reference_branch": "CONFIRMED_CANDIDATE", "available": True, "snapshot_timestamp": "2", "error": None},
        ]
        legitimate = [
            {"candidate_id": "L1", "reference_branch": "LEGITIMATE_CANDIDATE", "available": True, "snapshot_timestamp": "1", "error": None},
            {"candidate_id": "L2", "reference_branch": "LEGITIMATE_CANDIDATE", "available": True, "snapshot_timestamp": "2", "error": None},
            {"candidate_id": "L3", "reference_branch": "LEGITIMATE_CANDIDATE", "available": True, "snapshot_timestamp": "3", "error": None},
        ]
        selected = select_topup_pair(confirmed, legitimate, {"L1"}, seed="seed")
        self.assertEqual(len(selected), 4)
        self.assertEqual(sum(row["reference_branch"] == "CONFIRMED_CANDIDATE" for row in selected), 2)
        self.assertEqual(sum(row["reference_branch"] == "LEGITIMATE_CANDIDATE" for row in selected), 2)
        self.assertNotIn("L1", {row["candidate_id"] for row in selected})


if __name__ == "__main__":
    unittest.main()
