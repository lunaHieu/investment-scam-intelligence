import unittest
from datetime import datetime

from scripts.retry_sec_edgar_iapd_wayback_availability_v4 import cooldown_state, parse_time, request_url, unresolved_ids


class RetrySecEdgarIapdWaybackAvailabilityV4Tests(unittest.TestCase):
    def test_unresolved_ids_select_only_error_rows(self) -> None:
        report = {"results": [{"availability_plan_id": "A", "error": None}, {"availability_plan_id": "B", "error": "timeout"}]}
        self.assertEqual(unresolved_ids(report), ["B"])

    def test_request_url_encodes_candidate(self) -> None:
        value = request_url("https://archive.org/wayback/available", "https://example.test/a", "20261003")
        self.assertIn("example.test%2Fa", value)

    def test_cooldown_state_is_closed_before_not_before(self) -> None:
        release = {"cooldown_contract": {"not_before": "2026-10-16T00:48:55+07:00"}}
        ready, remaining = cooldown_state(release, datetime.fromisoformat("2026-10-15T01:48:55+07:00"))
        self.assertFalse(ready)
        self.assertEqual(remaining, 23 * 3600)

    def test_cooldown_state_opens_at_not_before(self) -> None:
        release = {"cooldown_contract": {"not_before": "2026-10-16T00:48:55+07:00"}}
        ready, remaining = cooldown_state(release, parse_time("2026-10-16T00:48:55+07:00"))
        self.assertTrue(ready)
        self.assertEqual(remaining, 0.0)


if __name__ == "__main__":
    unittest.main()
