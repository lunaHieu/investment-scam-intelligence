import json
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from scripts.execute_target_text_corpus_v1_ready_channel_wayback_availability_retry_v3 import coordination_evidence
from scripts.verify_target_text_corpus_v1_ready_channel_wayback_availability_retry_release_v3 import PASS_STATUS, verify


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "target_text_corpus_v1_ready_channel_wayback_availability_retry_release_v3.json"


class ReadyChannelWaybackAvailabilityRetryV3Tests(unittest.TestCase):
    def test_real_release_reproduces_two_prior_429_attempts(self) -> None:
        result = verify(RELEASE, require_output_absent=False)
        self.assertEqual(result["status"], PASS_STATUS, result["errors"])
        self.assertEqual(result["checks"]["plan_rows"], 70)
        self.assertEqual(result["checks"]["prior_trigger_row_attempts"], 2)
        self.assertTrue(result["checks"]["prior_http_429_without_retry_after"])

    def test_one_hour_gate_is_exact(self) -> None:
        release = json.loads(RELEASE.read_text(encoding="utf-8"))
        gate = datetime.fromisoformat(release["retry_policy"]["not_before"])
        observed = datetime.fromisoformat(release["retry_policy"]["observed_at"])
        self.assertEqual(gate - observed, timedelta(hours=1))
        with self.assertRaises(PermissionError):
            coordination_evidence(release, gate - timedelta(microseconds=1))
        evidence = coordination_evidence(release, gate)
        self.assertTrue(evidence["triggering_row_final_attempt"])

    def test_triggering_row_cannot_receive_a_fourth_identical_attempt(self) -> None:
        release = json.loads(RELEASE.read_text(encoding="utf-8"))
        policy = release["retry_policy"]
        self.assertEqual(policy["network_attempts_for_triggering_row"], 2)
        self.assertEqual(policy["maximum_network_attempts_per_artifact_family"], 3)
        self.assertFalse(policy["triggering_row_identical_retry_after_this_release_if_failed"])
        self.assertFalse(release["decision"]["previous_release_rerun_allowed"])


if __name__ == "__main__":
    unittest.main()
