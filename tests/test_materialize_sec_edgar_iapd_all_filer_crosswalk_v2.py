import unittest

from scripts.materialize_sec_edgar_iapd_all_filer_crosswalk_v2 import better


class MaterializeSecEdgarIapdAllFilerCrosswalkV2Tests(unittest.TestCase):
    def test_better_prefers_score_then_lexical_cik(self) -> None:
        self.assertTrue(better(0.9, "0000000002", (0.8, "0000000001", "A")))
        self.assertTrue(better(0.8, "0000000001", (0.8, "0000000002", "B")))
        self.assertFalse(better(0.7, "0000000001", (0.8, "0000000002", "B")))


if __name__ == "__main__":
    unittest.main()
