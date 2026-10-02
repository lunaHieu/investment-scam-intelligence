import unittest

from scripts.build_balanced_wayback_capture_plan_v2 import select_balanced


class BalancedWaybackCapturePlanV2Tests(unittest.TestCase):
    def test_selection_is_balanced_deterministic_and_available_only(self):
        rows = []
        for branch, prefix in (
            ("CONFIRMED_CANDIDATE", "C"),
            ("LEGITIMATE_CANDIDATE", "L"),
        ):
            for index in range(4):
                rows.append(
                    {
                        "candidate_id": f"{prefix}{index}",
                        "reference_branch": branch,
                        "available": True,
                        "snapshot_timestamp": f"2026010100000{index}",
                        "error": None,
                    }
                )
        selected, counts = select_balanced(rows, per_branch=2, seed="seed")
        again, _ = select_balanced(rows, per_branch=2, seed="seed")
        self.assertEqual(selected, again)
        self.assertEqual(counts, {"CONFIRMED_CANDIDATE": 2, "LEGITIMATE_CANDIDATE": 2})
        self.assertTrue(all(row["available"] for row in selected))

    def test_unresolved_errors_block_plan(self):
        with self.assertRaises(ValueError):
            select_balanced(
                [
                    {
                        "candidate_id": "C1",
                        "reference_branch": "CONFIRMED_CANDIDATE",
                        "available": False,
                        "snapshot_timestamp": None,
                        "error": "timeout",
                    }
                ],
                per_branch=1,
                seed="seed",
            )


if __name__ == "__main__":
    unittest.main()
