import unittest

from scripts.build_sec_edgar_iapd_crosswalk import stable_key, tokens


class BuildSecEdgarIapdCrosswalkTests(unittest.TestCase):
    def test_tokens_remove_legal_and_generic_terms(self):
        self.assertEqual(tokens("Alpha Ridge Capital Management, LLC"), {"alpha", "ridge"})

    def test_stable_key_is_deterministic_and_channel_bound(self):
        first = stable_key("seed", "0000123456", "example.test")
        second = stable_key("seed", "0000123456", "example.test")
        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)


if __name__ == "__main__":
    unittest.main()
