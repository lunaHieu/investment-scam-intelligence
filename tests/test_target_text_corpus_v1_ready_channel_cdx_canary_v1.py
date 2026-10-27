import json
import tempfile
import unittest
import urllib.error
import urllib.parse
from datetime import datetime
from email.message import Message
from pathlib import Path
from unittest.mock import patch

from scripts.execute_target_text_corpus_v1_ready_channel_cdx_canary_v1 import (
    CanaryRateLimitStop,
    USER_AGENT,
    build_request_url,
    execute,
    fetch_cdx,
    parse_metadata,
)
from scripts.verify_target_text_corpus_v1_ready_channel_cdx_canary_release_v1 import (
    PASS_STATUS,
    verify,
)


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "target_text_corpus_v1_ready_channel_cdx_canary_release_v1.json"
RELEASE_QA = Path(
    r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs"
    r"\ready_channel_wayback_availability_plan_v1\independent_cdx_canary_release_qa_v1.json"
)


class _RateLimitedOpener:
    def __init__(self) -> None:
        self.request = None

    def open(self, request, timeout):
        self.request = request
        headers = Message()
        headers["Retry-After"] = "7200"
        headers["Content-Type"] = "text/html"
        raise urllib.error.HTTPError(request.full_url, 429, "Too Many Requests", headers, None)


class ReadyChannelCdxCanaryV1Tests(unittest.TestCase):
    def test_real_release_passes_independent_verification(self) -> None:
        result = verify(RELEASE)
        self.assertEqual(result["status"], PASS_STATUS, result["errors"])
        self.assertEqual(result["checks"]["target_availability_plan_id"], "TTCV1_B3_AVAIL_002")
        self.assertEqual(result["checks"]["adaptive_delay_seconds"], 86400)

    def test_parser_accepts_canonical_empty_and_valid_table(self) -> None:
        release = json.loads(RELEASE.read_text(encoding="utf-8"))
        empty = parse_metadata(b"[]", release)
        self.assertEqual(empty["eligible_row_count"], 0)
        fields = release["cdx_contract"]["query"]["fields"]
        payload = json.dumps([
            fields,
            ["20261002120000", "https://carlylecapitalmanagement.com/", "200", "text/html", "A" * 32],
            ["20261002120001", "https://other.example/", "200", "text/html", "B" * 32],
        ]).encode()
        parsed = parse_metadata(payload, release)
        self.assertEqual(parsed["eligible_row_count"], 1)
        self.assertEqual(parsed["selected_candidate"]["timestamp"], "20261002120000")

    def test_request_is_one_metadata_only_cdx_call_and_preserves_429(self) -> None:
        release = json.loads(RELEASE.read_text(encoding="utf-8"))
        contract = release["cdx_contract"]
        url = build_request_url(contract)
        parsed = urllib.parse.urlsplit(url)
        self.assertEqual(parsed.hostname, "web.archive.org")
        self.assertEqual(parsed.path, "/cdx/search/cdx")
        opener = _RateLimitedOpener()
        counter = [0]
        with patch(
            "scripts.execute_target_text_corpus_v1_ready_channel_cdx_canary_v1.urllib.request.build_opener",
            return_value=opener,
        ), patch(
            "scripts.execute_target_text_corpus_v1_ready_channel_cdx_canary_v1.time.sleep"
        ) as sleeper:
            with self.assertRaises(CanaryRateLimitStop) as caught:
                fetch_cdx(url, contract, counter)
        self.assertEqual(counter, [1])
        self.assertEqual(caught.exception.diagnostics["http_status"], 429)
        self.assertEqual(opener.request.get_header("User-agent"), USER_AGENT)
        sleeper.assert_called_once_with(60.0)

    def test_executor_refuses_before_not_before_without_network(self) -> None:
        with patch(
            "scripts.execute_target_text_corpus_v1_ready_channel_cdx_canary_v1.fetch_cdx"
        ) as fetcher:
            with self.assertRaises(PermissionError):
                execute(
                    RELEASE,
                    RELEASE_QA,
                    now=datetime.fromisoformat("2026-10-27T12:00:00+07:00"),
                )
        fetcher.assert_not_called()


if __name__ == "__main__":
    unittest.main()
