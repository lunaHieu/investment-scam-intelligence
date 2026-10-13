import unittest

from scripts.verify_sec_edgar_iapd_all_filer_crosswalk_v2 import insert_top_two


class VerifySecEdgarIapdAllFilerCrosswalkV2Tests(unittest.TestCase):
    def test_insert_top_two_is_distinct_and_deterministic(self) -> None:
        values = []
        insert_top_two(values, 0.7, "0000000003")
        insert_top_two(values, 0.9, "0000000002")
        insert_top_two(values, 0.9, "0000000001")
        insert_top_two(values, 1.0, "0000000001")
        self.assertEqual(values, [(0.9, "0000000001"), (0.9, "0000000002")])


if __name__ == "__main__":
    unittest.main()
