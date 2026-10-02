import unittest

from scripts.prepare_pending_wayback_availability_v2 import pending_result


class PendingWaybackAvailabilityV2Tests(unittest.TestCase):
    def test_pending_state_is_not_no_snapshot(self):
        result = pending_result(
            {
                "candidate_id": "C1",
                "candidate_host": "Example.COM.",
                "source_case_id": "S1",
                "reference_branch": "CONFIRMED_CANDIDATE",
                "target_timestamp": "20261001",
            }
        )
        self.assertFalse(result["available"])
        self.assertEqual(result["error"], "PENDING_NETWORK_QUERY_NOT_AN_AVAILABILITY_RESULT")
        self.assertEqual(result["candidate_host"], "example.com")


if __name__ == "__main__":
    unittest.main()
