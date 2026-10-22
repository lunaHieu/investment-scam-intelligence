import unittest
from pathlib import Path

from scripts.verify_sec_edgar_iapd_wayback_alternate_snapshot_cdx_release_v1 import (
    FAILED_RESPONSE_SHA256,
    FAILED_TIMESTAMP,
    PASS_STATUS,
    TARGET_ID,
    verify,
)


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "sec_edgar_iapd_wayback_alternate_snapshot_cdx_release_v1.json"


class AlternateSnapshotCdxReleaseV1Tests(unittest.TestCase):
    def test_real_release_passes_independent_offline_verification(self) -> None:
        result = verify(RELEASE)
        self.assertEqual(result["status"], PASS_STATUS, result["errors"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["checks"]["target_availability_plan_id"], TARGET_ID)
        self.assertEqual(result["checks"]["failed_snapshot_timestamp_excluded"], FAILED_TIMESTAMP)
        self.assertEqual(result["checks"]["failed_response_sha256_pinned"], FAILED_RESPONSE_SHA256)
        self.assertEqual(result["checks"]["minimum_cooldown_seconds"], 86400)
        self.assertFalse(result["checks"]["archived_page_download_allowed"])


if __name__ == "__main__":
    unittest.main()
