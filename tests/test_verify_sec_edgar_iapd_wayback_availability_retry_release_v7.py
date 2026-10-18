import unittest
from pathlib import Path

from scripts.verify_sec_edgar_iapd_wayback_availability_retry_release_v7 import verify


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "sec_edgar_iapd_wayback_availability_retry_release_v7.json"


class VerifySecEdgarIapdWaybackAvailabilityRetryReleaseV7Tests(unittest.TestCase):
    def test_frozen_release_passes_independent_verification(self) -> None:
        result = verify(RELEASE)
        self.assertEqual(
            result["status"],
            "PASS_FROZEN_NOT_BEFORE_24H_UNRESOLVED_ONLY_CRASH_SAFE_PACING_PRESERVED",
        )
        self.assertEqual(result["checks"]["resolved_rows_preserved"], 107)
        self.assertEqual(result["checks"]["retry_rows"], 8)
        self.assertEqual(result["checks"]["unresolved_cohort_counts"], {"DEVELOPMENT": 4, "EXTERNAL_HOLDOUT": 4})
        self.assertEqual(result["errors"], [])

if __name__ == "__main__":
    unittest.main()
