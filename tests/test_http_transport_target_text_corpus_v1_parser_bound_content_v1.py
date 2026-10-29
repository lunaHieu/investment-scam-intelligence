import io
import json
import unittest
import urllib.error
from email.message import Message
from unittest.mock import patch

from scripts.http_transport_target_text_corpus_v1_parser_bound_content_v1 import (
    authorize_live_transport,
    fetch_with_injected_opener,
    live_transport,
)
from scripts.verify_target_text_corpus_v1_parser_bound_content_release_v1 import RELEASE


def resources():
    return json.loads(RELEASE.read_text(encoding="utf-8"))["resources"]


class FakeResponse(io.BytesIO):
    def __init__(self, body: bytes, content_type: str, status: int = 200):
        super().__init__(body)
        self.status = status
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def getcode(self):
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class SequenceOpener:
    def __init__(self, sequence):
        self.sequence = list(sequence)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        item = self.sequence.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def redirect_error(url: str, location: str, code: int = 307):
    headers = Message()
    headers["Location"] = location
    return urllib.error.HTTPError(url, code, "Redirect", headers, None)


class ParserBoundHttpTransportV1Tests(unittest.TestCase):
    def test_live_capability_is_closed_while_candidate_is_uncommitted(self):
        with self.assertRaises(PermissionError):
            authorize_live_transport()

    def test_invalid_capability_blocks_before_real_opener_is_built(self):
        with patch("scripts.http_transport_target_text_corpus_v1_parser_bound_content_v1.urllib.request.build_opener") as builder:
            with self.assertRaises(PermissionError):
                live_transport(resources()[0], object())
            builder.assert_not_called()

    def test_injected_success_uses_pinned_headers_and_timeout(self):
        resource = resources()[0]
        opener = SequenceOpener([FakeResponse(b"{}", "application/json")])
        response = fetch_with_injected_opener(resource, opener)
        request, timeout = opener.requests[0]
        self.assertEqual(response.body, b"{}")
        self.assertEqual(timeout, 30)
        self.assertIn("ISI-ParserBoundContent/1.0", request.get_header("User-agent"))
        self.assertIn("github.com/lunaHieu/investment-scam-intelligence", request.get_header("User-agent"))
        self.assertEqual(request.get_header("Accept"), "application/json")

    def test_bounded_stream_reads_at_most_limit_plus_one(self):
        resource = resources()[3]
        oversized = b"x" * (resource["maximum_bytes"] + 500)
        opener = SequenceOpener([FakeResponse(oversized, "text/plain")])
        response = fetch_with_injected_opener(resource, opener)
        self.assertEqual(len(response.body), resource["maximum_bytes"] + 1)

    def test_only_pinned_markdown_redirect_is_followed_once(self):
        resource = resources()[6]
        final_url = (
            "https://huggingface.co/datasets/trannguyenthaituan/"
            "vietnamese_sms_dataset/resolve/"
            "a90e2bd7e8df2376939658075ba8094dcee488ad/QUICKSTART_GUIDE.md"
        )
        opener = SequenceOpener([
            redirect_error(resource["url"], final_url),
            FakeResponse(b"# Files\nmetadata", "text/plain"),
        ])
        response = fetch_with_injected_opener(resource, opener)
        self.assertEqual(response.redirect_count, 1)
        self.assertEqual(response.final_url, final_url)
        self.assertEqual(len(opener.requests), 2)

    def test_redirect_for_non_redirect_resource_fails_closed(self):
        resource = resources()[0]
        opener = SequenceOpener([redirect_error(resource["url"], "https://huggingface.co/wrong")])
        with self.assertRaises(ValueError):
            fetch_with_injected_opener(resource, opener)

    def test_http_error_body_is_not_read_and_request_is_not_retried(self):
        resource = resources()[3]
        headers = Message()
        headers["Content-Type"] = "text/plain"
        error = urllib.error.HTTPError(
            resource["url"], 429, "Too Many Requests", headers,
            io.BytesIO(b"x" * (resource["maximum_bytes"] + 100)),
        )
        opener = SequenceOpener([error])
        response = fetch_with_injected_opener(resource, opener)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.body, b"")
        self.assertEqual(error.fp.tell(), 0)
        self.assertEqual(len(opener.requests), 1)


if __name__ == "__main__":
    unittest.main()
