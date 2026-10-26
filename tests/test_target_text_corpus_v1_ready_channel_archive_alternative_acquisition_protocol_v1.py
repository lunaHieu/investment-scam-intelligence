import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_ready_channel_archive_alternative_acquisition_protocol_v1 import PASS_STATUS, verify


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "configs" / "target_text_corpus_v1_ready_channel_archive_alternative_acquisition_protocol_v1.json"


class ReadyChannelArchiveAlternativeAcquisitionProtocolV1Tests(unittest.TestCase):
    def test_real_protocol_is_conditional_finite_and_metadata_only(self) -> None:
        result = verify(PROTOCOL)
        self.assertEqual(result["status"], PASS_STATUS, result["errors"])
        self.assertEqual(result["checks"]["continuation_rows"], 69)
        self.assertEqual(result["checks"]["canary_rows"], 1)
        self.assertEqual(result["checks"]["canary_id"], "TTCV1_B3_AVAIL_002")
        self.assertTrue(result["checks"]["metadata_only"])
        self.assertFalse(result["decision"]["network_execution_allowed_now"])

    def test_fallback_does_not_bypass_continuation_or_reopen_row_001(self) -> None:
        protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
        self.assertTrue(protocol["activation_contract"]["continuation_must_execute_first"])
        self.assertTrue(protocol["activation_contract"]["activation_on_complete_continuation_forbidden"])
        self.assertFalse(protocol["decision"]["continuation_bypassed"])
        self.assertFalse(protocol["decision"]["quarantined_row_retry_allowed"])

    def test_canary_has_one_request_and_no_automatic_cascade(self) -> None:
        protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
        self.assertEqual(protocol["canary_contract"]["maximum_logical_requests"], 1)
        self.assertEqual(protocol["canary_contract"]["maximum_attempts"], 1)
        self.assertEqual(protocol["branch_contract"]["maximum_identical_canary_attempts"], 1)
        self.assertFalse(protocol["branch_contract"]["automatic_fallback_cascade_allowed"])


if __name__ == "__main__":
    unittest.main()
