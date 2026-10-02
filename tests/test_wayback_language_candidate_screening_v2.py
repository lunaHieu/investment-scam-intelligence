import unittest

from scripts.screen_wayback_language_candidates_v2 import merge_profiles


class WaybackLanguageCandidateScreeningV2Tests(unittest.TestCase):
    def test_profile_merge_is_unique_and_sorted(self):
        rows = merge_profiles([[{"candidate_id": "B"}], [{"candidate_id": "A"}]])
        self.assertEqual([row["candidate_id"] for row in rows], ["A", "B"])

    def test_profile_overlap_is_rejected(self):
        with self.assertRaises(ValueError):
            merge_profiles([[{"candidate_id": "A"}], [{"candidate_id": "A"}]])


if __name__ == "__main__":
    unittest.main()
