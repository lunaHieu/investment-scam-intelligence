import json
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.orchestrate_target_text_corpus_v1_parser_bound_content_v1 import execute_live
from scripts.http_transport_target_text_corpus_v1_parser_bound_content_v1 import authorize_live_transport
from scripts.verify_target_text_corpus_v1_parser_bound_content_result_v1 import (
    DEFAULT_RESULT,
    verify_result,
)
from scripts.verify_target_text_corpus_v1_parser_bound_content_release_v1 import ROOT


class CurrentArtifactLifecycleV8Tests(unittest.TestCase):
    def test_parser_bound_result_is_pinned_and_independently_verified(self):
        result = verify_result(DEFAULT_RESULT)
        self.assertEqual(result["status"], "PASS_PARSER_BOUND_CONTENT_RESULT_VERIFIED")
        self.assertEqual((result["success"], result["parser_rejected"], result["skipped_after_failure"]), (4, 1, 3))

    def test_parser_bound_result_keeps_downstream_gates_closed(self):
        value = json.loads(DEFAULT_RESULT.read_text(encoding="utf-8"))
        self.assertFalse(value["decision"]["evidence_acceptance_allowed"])
        self.assertFalse(value["decision"]["dataset_acquisition_allowed"])
        self.assertFalse(value["decision"]["training_allowed"])

    def test_parser_bound_result_retains_no_raw_or_temporary_artifacts(self):
        value = json.loads(DEFAULT_RESULT.read_text(encoding="utf-8"))
        self.assertTrue(all(row["raw_response_retained"] is False for row in value["resources"]))
        temp_root = ROOT / "tmp" / "pdfs"
        self.assertEqual(list(temp_root.rglob("*")) if temp_root.exists() else [], [])
        self.assertFalse(Path(str(DEFAULT_RESULT) + ".partial").exists())
        self.assertFalse(Path(str(DEFAULT_RESULT) + ".partial.tmp").exists())

    def test_historical_readiness_audit_snapshot_remains_closed(self):
        audit_path = ROOT / "registry" / "analyses" / "target_text_corpus_v1_parser_bound_execution_readiness_audit_local_v1.json"
        value = json.loads(audit_path.read_text(encoding="utf-8"))
        self.assertEqual(value["status"], "PASS_STACK_INTEGRITY_VERIFIED_EXECUTION_REMAINS_CLOSED")
        self.assertFalse(value["decision"]["execution_allowed"])

    def test_original_v1_rerun_is_blocked_before_real_opener(self):
        with patch("scripts.http_transport_target_text_corpus_v1_parser_bound_content_v1.urllib.request.build_opener") as opener:
            with self.assertRaises(FileExistsError):
                execute_live()
            opener.assert_not_called()

    def test_original_v1_http_capability_is_unavailable_after_result(self):
        with patch("scripts.http_transport_target_text_corpus_v1_parser_bound_content_v1.urllib.request.build_opener") as opener:
            with self.assertRaises(FileExistsError):
                authorize_live_transport()
            opener.assert_not_called()

    def test_original_owner_amendment_is_historical_and_result_is_pinned(self):
        amendment = ROOT / "configs" / "target_text_corpus_v1_parser_bound_content_execution_amendment_v1.json"
        value = json.loads(amendment.read_text(encoding="utf-8"))
        self.assertEqual(value["status"], "OWNER_AUTHORIZED_PENDING_COMMITTED_QA")
        self.assertTrue(DEFAULT_RESULT.is_file())
        self.assertEqual(verify_result(DEFAULT_RESULT)["status"], "PASS_PARSER_BOUND_CONTENT_RESULT_VERIFIED")

    def test_original_authorization_protocol_is_historical_and_closed(self):
        protocol = ROOT / "configs" / "target_text_corpus_v1_parser_bound_content_execution_authorization_protocol_v1.json"
        value = json.loads(protocol.read_text(encoding="utf-8"))
        self.assertFalse(value["decision"]["network_execution_allowed_now"])
        self.assertTrue(DEFAULT_RESULT.is_file())


if __name__ == "__main__":
    unittest.main()
