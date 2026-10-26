import json
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from scripts.execute_target_text_corpus_v1_ready_channel_wayback_availability_v2 import coordination_evidence
from scripts.verify_target_text_corpus_v1_ready_channel_wayback_availability_execution_amendment_v2 import PASS_STATUS, verify


ROOT = Path(__file__).resolve().parents[1]
AMENDMENT = ROOT / "configs" / "target_text_corpus_v1_ready_channel_wayback_availability_execution_amendment_v2.json"


class ReadyChannelAvailabilityExecutionAmendmentV2Tests(unittest.TestCase):
    def test_real_amendment_recomputes_canonical_empty_and_exact_70(self) -> None:
        result = verify(AMENDMENT)
        self.assertEqual(result["status"], PASS_STATUS, result["errors"])
        self.assertEqual(result["checks"]["plan_rows"], 70)
        self.assertFalse(result["checks"]["a1_rate_limit"])
        self.assertFalse(result["checks"]["a1_retry_needed"])
        self.assertTrue(result["checks"]["output_absent"])

    def test_gate_is_exact_and_already_independent_of_a1_parser_error(self) -> None:
        amendment = json.loads(AMENDMENT.read_text(encoding="utf-8"))
        gate = datetime.fromisoformat(amendment["coordination_contract"]["effective_not_before"])
        with self.assertRaises(PermissionError):
            coordination_evidence(amendment, gate - timedelta(microseconds=1))
        evidence = coordination_evidence(amendment, gate)
        self.assertEqual(evidence["a1_root_cause"], "PARSER_DID_NOT_ACCEPT_VALID_ZERO_ROW_CDX_JSON")
        self.assertFalse(evidence["a1_rate_limit"])

    def test_no_new_universal_24h_retry_chain(self) -> None:
        amendment = json.loads(AMENDMENT.read_text(encoding="utf-8"))
        policy = amendment["retry_policy"]
        self.assertTrue(policy["universal_fixed_24h_retry_forbidden"])
        self.assertEqual(policy["maximum_network_attempts_per_artifact_family"], 3)
        self.assertFalse(policy["b5_same_release_rerun_allowed"])


if __name__ == "__main__":
    unittest.main()
