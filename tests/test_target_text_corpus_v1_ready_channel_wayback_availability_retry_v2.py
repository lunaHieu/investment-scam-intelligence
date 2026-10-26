import json
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from scripts.execute_target_text_corpus_v1_ready_channel_wayback_availability_retry_v2 import coordination_evidence
from scripts.verify_target_text_corpus_v1_ready_channel_wayback_availability_retry_release_v2 import PASS_STATUS, verify


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "target_text_corpus_v1_ready_channel_wayback_availability_retry_release_v2.json"


class ReadyChannelWaybackAvailabilityRetryV2Tests(unittest.TestCase):
    def test_real_release_is_exact_70_and_policy_recomputes(self) -> None:
        result = verify(RELEASE, require_output_absent=False)
        self.assertEqual(result["status"], PASS_STATUS, result["errors"])
        self.assertEqual(result["checks"]["plan_rows"], 70)
        self.assertEqual(result["checks"]["development_rows"], 50)
        self.assertEqual(result["checks"]["external_holdout_rows"], 20)
        self.assertTrue(result["checks"]["previous_http_429_without_retry_after"])
        self.assertEqual(result["checks"]["adaptive_policy_id"], "ISI_ARCHIVE_RETRY_POLICY_V1")

    def test_retry_gate_is_exact(self) -> None:
        release = json.loads(RELEASE.read_text(encoding="utf-8"))
        gate = datetime.fromisoformat(release["retry_policy"]["not_before"])
        with self.assertRaises(PermissionError):
            coordination_evidence(release, gate - timedelta(microseconds=1))
        evidence = coordination_evidence(release, gate)
        self.assertEqual(evidence["not_before"], gate.isoformat())
        self.assertEqual(evidence["consecutive_failures_before_release"], 1)
        self.assertTrue(evidence["universal_fixed_24h_retry_forbidden"])

    def test_parent_release_cannot_be_rerun(self) -> None:
        release = json.loads(RELEASE.read_text(encoding="utf-8"))
        self.assertFalse(release["identity_contract"]["same_parent_release_rerun"])
        self.assertFalse(release["decision"]["parent_release_rerun_allowed"])
        self.assertEqual(release["retry_policy"]["maximum_network_attempts_per_artifact_family"], 3)


if __name__ == "__main__":
    unittest.main()
