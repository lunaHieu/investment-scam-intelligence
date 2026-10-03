import unittest

from scripts.normalize_sec_edgar_shortlist import jaccard


class NormalizeSecEdgarShortlistTests(unittest.TestCase):
    def test_jaccard_requires_substantial_token_agreement(self):
        self.assertEqual(jaccard({"alpha", "ridge"}, {"alpha", "ridge"}), 1.0)
        self.assertAlmostEqual(jaccard({"alpha", "ridge"}, {"alpha", "harbor"}), 1 / 3)
        self.assertEqual(jaccard(set(), set()), 0.0)


if __name__ == "__main__":
    unittest.main()
