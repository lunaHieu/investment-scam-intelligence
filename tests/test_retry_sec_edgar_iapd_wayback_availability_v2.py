import unittest

from scripts.retry_sec_edgar_iapd_wayback_availability_v2 import request_url, unresolved_ids


class RetrySecEdgarIapdWaybackAvailabilityV2Tests(unittest.TestCase):
    def test_unresolved_ids_select_only_error_rows(self) -> None:
        report = {"results": [{"availability_plan_id": "A", "error": None}, {"availability_plan_id": "B", "error": "timeout"}]}
        self.assertEqual(unresolved_ids(report), ["B"])

    def test_request_url_encodes_candidate(self) -> None:
        value = request_url("https://archive.org/wayback/available", "https://example.test/a", "20261003")
        self.assertIn("example.test%2Fa", value)


if __name__ == "__main__":
    unittest.main()
