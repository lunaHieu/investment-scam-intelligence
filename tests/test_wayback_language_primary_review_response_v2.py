import unittest

from scripts.build_wayback_language_primary_review_response_v2 import invert_roster


class WaybackLanguagePrimaryReviewResponseV2Tests(unittest.TestCase):
    def test_roster_must_cover_each_candidate_once(self):
        self.assertEqual(invert_roster({"A": ["1"], "B": ["2"]}, {"1", "2"}, "x"), {"1": "A", "2": "B"})
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            invert_roster({"A": ["1"], "B": ["1"]}, {"1"}, "x")
        with self.assertRaisesRegex(ValueError, "coverage mismatch"):
            invert_roster({"A": ["1"]}, {"1", "2"}, "x")


if __name__ == "__main__":
    unittest.main()
