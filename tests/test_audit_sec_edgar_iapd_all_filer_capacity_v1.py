import unittest

from scripts.audit_sec_edgar_iapd_all_filer_capacity_v1 import update_top_two


class AuditSecEdgarIapdAllFilerCapacityV1Tests(unittest.TestCase):
    def test_top_two_are_score_then_cik_deterministic(self) -> None:
        best = [(0.0, "")]
        second = [(0.0, "")]
        update_top_two(best, second, 0, 0.8, "0000000002")
        update_top_two(best, second, 0, 0.8, "0000000001")
        update_top_two(best, second, 0, 0.6, "0000000003")
        self.assertEqual(best[0], (0.8, "0000000001"))
        self.assertEqual(second[0], (0.8, "0000000002"))

    def test_new_best_demotes_old_best(self) -> None:
        best = [(0.0, "")]
        second = [(0.0, "")]
        update_top_two(best, second, 0, 0.7, "0000000001")
        update_top_two(best, second, 0, 1.0, "0000000002")
        self.assertEqual(best[0], (1.0, "0000000002"))
        self.assertEqual(second[0], (0.7, "0000000001"))


if __name__ == "__main__":
    unittest.main()
