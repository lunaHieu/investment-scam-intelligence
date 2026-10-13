import unittest

from scripts.verify_sec_edgar_iapd_wayback_availability_result_v2 import canonical


class VerifySecEdgarIapdWaybackAvailabilityResultV2Tests(unittest.TestCase):
    def test_canonical_is_key_order_independent(self) -> None:
        self.assertEqual(canonical({"a": 1, "b": 2}), canonical({"b": 2, "a": 1}))


if __name__ == "__main__":
    unittest.main()
