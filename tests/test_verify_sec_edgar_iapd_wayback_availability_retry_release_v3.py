import unittest
from pathlib import Path

from scripts.verify_sec_edgar_iapd_wayback_availability_retry_release_v3 import verify


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "sec_edgar_iapd_wayback_availability_retry_release_v3.json"


class VerifySecEdgarIapdWaybackAvailabilityRetryReleaseV3Tests(unittest.TestCase):
    def test_frozen_release_passes_independent_offline_verification(self) -> None:
        result = verify(RELEASE)
        self.assertEqual(result["status"], "PASS_FROZEN_NOT_BEFORE_24H_UNRESOLVED_ONLY")
        self.assertEqual(result["checks"]["resolved_rows_preserved"], 45)
        self.assertEqual(result["checks"]["retry_rows"], 70)
        self.assertEqual(result["checks"]["minimum_cooldown_seconds"], 86400)
        self.assertEqual(result["errors"], [])


if __name__ == "__main__":
    unittest.main()
