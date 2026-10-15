import unittest
from pathlib import Path

from scripts.verify_sec_edgar_iapd_wayback_availability_retry_release_v5 import verify


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "sec_edgar_iapd_wayback_availability_retry_release_v5.json"


class VerifySecEdgarIapdWaybackAvailabilityRetryReleaseV5Tests(unittest.TestCase):
    def test_frozen_release_passes_independent_verification(self) -> None:
        result = verify(RELEASE)
        self.assertEqual(result["status"], "PASS_FROZEN_NOT_BEFORE_24H_UNRESOLVED_ONLY_SLOWER_PACING")
        self.assertEqual(result["checks"]["resolved_rows_preserved"], 92)
        self.assertEqual(result["checks"]["retry_rows"], 23)
        self.assertEqual(result["checks"]["minimum_delay_seconds"], 60.0)
        self.assertEqual(result["errors"], [])


if __name__ == "__main__":
    unittest.main()
