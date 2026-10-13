import unittest

from scripts.verify_sec_edgar_iapd_wayback_availability_plan_v1 import decode_planned_request, expected_plan_id


class VerifySecEdgarIapdWaybackAvailabilityPlanV1Tests(unittest.TestCase):
    def test_decode_planned_request_recovers_exact_values(self) -> None:
        url, timestamp = decode_planned_request("https://archive.org/wayback/available?url=https%3A%2F%2Fexample.test%2Fa&timestamp=20261003")
        self.assertEqual(url, "https://example.test/a")
        self.assertEqual(timestamp, "20261003")

    def test_decode_planned_request_rejects_candidate_endpoint(self) -> None:
        with self.assertRaises(ValueError):
            decode_planned_request("https://example.test/wayback/available?url=https%3A%2F%2Fx.test&timestamp=20261003")

    def test_expected_plan_ids_separate_cohorts(self) -> None:
        self.assertEqual(expected_plan_id("DEVELOPMENT", 1), "TTCV1_EDGAR_AVAIL_DEV_001")
        self.assertEqual(expected_plan_id("EXTERNAL_HOLDOUT", 1), "TTCV1_EDGAR_AVAIL_HOLDOUT_001")


if __name__ == "__main__":
    unittest.main()
