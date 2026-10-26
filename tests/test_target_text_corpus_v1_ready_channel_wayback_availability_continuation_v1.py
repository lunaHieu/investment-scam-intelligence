import json
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from scripts.execute_target_text_corpus_v1_ready_channel_wayback_availability_continuation_v1 import coordination_evidence
from scripts.verify_target_text_corpus_v1_ready_channel_wayback_availability_continuation_release_v1 import PASS_STATUS, continuation_plan, read_plan, verify


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "target_text_corpus_v1_ready_channel_wayback_availability_continuation_release_v1.json"


class ReadyChannelWaybackAvailabilityContinuationV1Tests(unittest.TestCase):
    def test_real_release_is_exact_69_and_quarantines_trigger(self) -> None:
        result = verify(RELEASE, require_output_absent=False)
        self.assertEqual(result["status"], PASS_STATUS, result["errors"])
        self.assertEqual(result["checks"]["continuation_rows"], 69)
        self.assertEqual(result["checks"]["development_rows"], 49)
        self.assertEqual(result["checks"]["external_holdout_rows"], 20)
        self.assertEqual(result["checks"]["quarantined_ids"], ["TTCV1_B3_AVAIL_001"])

    def test_filter_preserves_order_and_excludes_only_trigger(self) -> None:
        release = json.loads(RELEASE.read_text(encoding="utf-8"))
        plan = continuation_plan(release, read_plan(Path(release["inputs"]["availability_plan"]["path"])))
        self.assertEqual([row["availability_plan_id"] for row in plan], [f"TTCV1_B3_AVAIL_{index:03d}" for index in range(2, 71)])

    def test_six_hour_circuit_breaker_gate_is_exact(self) -> None:
        release = json.loads(RELEASE.read_text(encoding="utf-8"))
        policy = release["circuit_breaker_policy"]
        observed, gate = datetime.fromisoformat(policy["observed_at"]), datetime.fromisoformat(policy["not_before"])
        self.assertEqual(gate - observed, timedelta(hours=6))
        with self.assertRaises(PermissionError):
            coordination_evidence(release, gate - timedelta(microseconds=1))
        evidence = coordination_evidence(release, gate)
        self.assertEqual(evidence["quarantined_availability_plan_ids"], ["TTCV1_B3_AVAIL_001"])
        self.assertTrue(evidence["universal_fixed_24h_retry_forbidden"])


if __name__ == "__main__":
    unittest.main()
