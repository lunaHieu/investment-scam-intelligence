import unittest
from pathlib import Path

from scripts.verify_sec_edgar_iapd_wayback_availability_v11_protocol_v1 import (
    EXPECTED_IDS,
    PASS_STATUS,
    verify,
)


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "configs" / "sec_edgar_iapd_wayback_availability_v11_protocol_v1.json"


class AvailabilityV11ProtocolV1Tests(unittest.TestCase):
    def test_real_protocol_passes_exact_two_row_offline_verification(self) -> None:
        result = verify(PROTOCOL)
        self.assertEqual(result["status"], PASS_STATUS, result["errors"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["checks"]["ordered_retry_ids"], EXPECTED_IDS)
        self.assertEqual(result["checks"]["retry_cohort"], "EXTERNAL_HOLDOUT")
        self.assertEqual(result["checks"]["minimum_delay_seconds"], 60.0)
        self.assertTrue(result["checks"]["concrete_release_required"])
        self.assertFalse(result["checks"]["network_execution_allowed"])


if __name__ == "__main__":
    unittest.main()
