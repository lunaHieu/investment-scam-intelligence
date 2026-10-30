import unittest
from unittest.mock import patch

from scripts.http_transport_target_text_corpus_v1_parser_bound_content_supplemental_v1 import (
    authorize_live_transport,
    execution_preflight,
    live_transport,
)
from scripts.verify_target_text_corpus_v1_parser_bound_content_supplemental_execution_authorization_v1 import (
    AMENDMENT_PASS,
    PROTOCOL_PASS,
    verify_optional_amendment,
    verify_protocol,
)


class ParserBoundSupplementalLiveGateV1Tests(unittest.TestCase):
    def test_protocol_and_exact_owner_amendment_verify(self):
        self.assertEqual(verify_protocol()["status"], PROTOCOL_PASS)
        self.assertEqual(verify_optional_amendment()["status"], AMENDMENT_PASS)

    def test_preflight_is_closed_before_owner_amendment_and_commit(self):
        result = execution_preflight()
        self.assertEqual(result["status"], "SUPPLEMENTAL_EXECUTION_PREFLIGHT_CLOSED")
        self.assertTrue(result["owner_amendment_verified"])
        self.assertFalse(result["execution_allowed"])
        with patch("scripts.http_transport_target_text_corpus_v1_parser_bound_content_supplemental_v1.urllib.request.build_opener") as opener:
            with self.assertRaises(PermissionError):
                authorize_live_transport()
            opener.assert_not_called()

    def test_forged_capability_cannot_construct_opener(self):
        with patch("scripts.http_transport_target_text_corpus_v1_parser_bound_content_supplemental_v1.urllib.request.build_opener") as opener:
            with self.assertRaises(PermissionError):
                live_transport({}, object())
            opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
