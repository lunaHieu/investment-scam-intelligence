import unittest

from scripts.interleave_wayback_retry_input_v2 import interleave_error_results


class WaybackRetryInterleaveTests(unittest.TestCase):
    def test_unresolved_branches_are_round_robin_and_resolved_are_preserved(self):
        rows = [
            {"candidate_id": "C2", "reference_branch": "CONFIRMED_CANDIDATE", "error": "x"},
            {"candidate_id": "L1", "reference_branch": "LEGITIMATE_CANDIDATE", "error": "x"},
            {"candidate_id": "C1", "reference_branch": "CONFIRMED_CANDIDATE", "error": "x"},
            {"candidate_id": "R1", "reference_branch": "LEGITIMATE_CANDIDATE", "error": None},
        ]
        ordered = interleave_error_results(rows)
        self.assertEqual([row["candidate_id"] for row in ordered], ["C1", "L1", "C2", "R1"])
        self.assertEqual({row["candidate_id"] for row in ordered}, {"C1", "C2", "L1", "R1"})

    def test_unknown_unresolved_branch_is_rejected(self):
        with self.assertRaises(ValueError):
            interleave_error_results(
                [{"candidate_id": "X", "reference_branch": "UNKNOWN", "error": "x"}]
            )


if __name__ == "__main__":
    unittest.main()
