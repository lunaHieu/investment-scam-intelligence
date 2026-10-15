import unittest
from datetime import datetime
from pathlib import Path

from scripts.retry_sec_edgar_iapd_wayback_availability_v4 import cooldown_state
from scripts.retry_sec_edgar_iapd_wayback_availability_v5 import validate_release


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "sec_edgar_iapd_wayback_availability_retry_release_v5.json"


class RetrySecEdgarIapdWaybackAvailabilityV5Tests(unittest.TestCase):
    def test_release_selects_exact_23_unresolved_rows(self) -> None:
        release, prior = validate_release(RELEASE)
        self.assertEqual(sum(row["error"] is not None for row in prior["results"]), 23)
        self.assertEqual(release["retry_contract"]["minimum_delay_seconds"], 60.0)

    def test_cooldown_fails_closed_before_not_before(self) -> None:
        release, _ = validate_release(RELEASE)
        ready, remaining = cooldown_state(release, datetime.fromisoformat("2026-10-17T01:19:26.607186+07:00"))
        self.assertFalse(ready)
        self.assertEqual(remaining, 1.0)

    def test_cooldown_opens_at_not_before(self) -> None:
        release, _ = validate_release(RELEASE)
        ready, remaining = cooldown_state(release, datetime.fromisoformat(release["cooldown_contract"]["not_before"]))
        self.assertTrue(ready)
        self.assertEqual(remaining, 0.0)


if __name__ == "__main__":
    unittest.main()
