import json
import unittest
from unittest.mock import patch

from scripts.http_transport_target_text_corpus_v1_parser_bound_content_v2 import (
    authorize_live_transport_v2,
    execution_preflight_v2,
    live_transport_v2,
)
from scripts.verify_target_text_corpus_v1_parser_bound_content_execution_amendment_v1 import (
    PASS_STATUS,
    verify,
    verify_registered_qa,
)


class ParserBoundExecutionAmendmentV1Tests(unittest.TestCase):
    def test_owner_authorized_scope_verifies_without_expanding_git_permission(self):
        result = verify()
        self.assertEqual(result["status"], PASS_STATUS)
        self.assertEqual(result["checks"]["resource_count"], 8)
        self.assertTrue(result["checks"]["owner_network_authorization_received"])
        self.assertFalse(result["checks"]["commit_authorized"])
        self.assertFalse(result["checks"]["push_authorized"])
        self.assertFalse(result["decision"]["network_execution_allowed_now"])

    def test_uncommitted_amendment_keeps_live_capability_closed(self):
        self.assertTrue(verify_registered_qa()["valid"])
        preflight = execution_preflight_v2()
        self.assertEqual(preflight["status"], "EXECUTION_PREFLIGHT_CLOSED")
        self.assertFalse(preflight["execution_allowed"])
        with patch("scripts.http_transport_target_text_corpus_v1_parser_bound_content_v2.urllib.request.build_opener") as opener:
            with self.assertRaises(PermissionError):
                authorize_live_transport_v2()
            opener.assert_not_called()

    def test_forged_capability_cannot_build_opener(self):
        with patch("scripts.http_transport_target_text_corpus_v1_parser_bound_content_v2.urllib.request.build_opener") as opener:
            with self.assertRaises(PermissionError):
                live_transport_v2({}, object())
            opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
