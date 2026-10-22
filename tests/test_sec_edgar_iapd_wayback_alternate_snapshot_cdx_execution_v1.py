import json
import tempfile
import unittest
import urllib.error
import urllib.parse
from email.message import Message
from pathlib import Path
from unittest.mock import patch

from scripts.execute_sec_edgar_iapd_wayback_alternate_snapshot_cdx_v1 import (
    CdxRateLimitStop,
    USER_AGENT,
    build_request_url,
    fetch_cdx,
    parse_and_select,
)


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "sec_edgar_iapd_wayback_alternate_snapshot_cdx_release_v1.json"


def minimal_release() -> dict:
    return {
        "target_record": {
            "availability_plan_id": "TTCV1_EDGAR_AVAIL_DEV_037",
            "candidate_host": "lionpoint.com",
            "failed_snapshot_timestamp": "20260210193325",
            "excluded_snapshot_timestamps": ["20260210193325"],
        },
        "cdx_contract": {
            "query": {
                "fields": ["timestamp", "original", "statuscode", "mimetype", "digest"],
                "maximum_rows": 1000,
            },
            "eligible_mimetypes": ["text/html"],
            "selection_rule": (
                "MIN_ABSOLUTE_TIME_DISTANCE_THEN_EARLIER_TIMESTAMP_THEN_ORIGINAL_THEN_DIGEST"
            ),
        },
    }


class _RateLimitedOpener:
    def __init__(self) -> None:
        self.request = None

    def open(self, request, timeout):
        self.request = request
        headers = Message()
        headers["Retry-After"] = "7200"
        headers["Date"] = "Thu, 22 Oct 2026 17:00:00 GMT"
        headers["Server"] = "nginx"
        raise urllib.error.HTTPError(request.full_url, 429, "Too Many Requests", headers, None)


class AlternateSnapshotCdxExecutionV1Tests(unittest.TestCase):
    def test_selection_excludes_failed_timestamp_and_uses_frozen_tie_break(self) -> None:
        fields = ["timestamp", "original", "statuscode", "mimetype", "digest"]
        payload = json.dumps(
            [
                fields,
                ["20260210193325", "https://lionpoint.com/", "200", "text/html", "A" * 32],
                ["20260209193325", "http://lionpoint.com/", "200", "text/html", "B" * 32],
                ["20260211193325", "https://www.lionpoint.com/", "200", "text/html", "C" * 32],
                ["20260210193324", "https://other.example/", "200", "text/html", "D" * 32],
            ]
        ).encode()
        result = parse_and_select(payload, minimal_release())
        self.assertEqual(result["eligible_row_count"], 2)
        self.assertEqual(result["selected_candidate"]["timestamp"], "20260209193325")
        self.assertNotEqual(result["selected_candidate"]["timestamp"], "20260210193325")
        self.assertEqual(
            result["selected_candidate"]["requested_archive_url"],
            "https://web.archive.org/web/20260209193325id_/http://lionpoint.com/",
        )

    def test_frozen_request_url_targets_only_archive_cdx(self) -> None:
        release = json.loads(RELEASE.read_text(encoding="utf-8"))
        url = build_request_url(release["cdx_contract"])
        parsed = urllib.parse.urlsplit(url)
        query = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(parsed.hostname, "web.archive.org")
        self.assertEqual(parsed.path, "/cdx/search/cdx")
        self.assertEqual(query["url"], ["lionpoint.com/"])
        self.assertEqual(query["matchType"], ["exact"])
        self.assertIn("timestamp:!20260210193325", query["filter"])

    def test_http_429_preserves_headers_and_has_no_automatic_retry(self) -> None:
        release = json.loads(RELEASE.read_text(encoding="utf-8"))
        contract = release["cdx_contract"]
        opener = _RateLimitedOpener()
        counter = [0]
        with patch(
            "scripts.execute_sec_edgar_iapd_wayback_alternate_snapshot_cdx_v1.urllib.request.build_opener",
            return_value=opener,
        ), patch(
            "scripts.execute_sec_edgar_iapd_wayback_alternate_snapshot_cdx_v1.time.sleep"
        ) as sleeper:
            with self.assertRaises(CdxRateLimitStop) as caught:
                fetch_cdx(build_request_url(contract), contract, counter)
        self.assertEqual(counter, [1])
        self.assertEqual(caught.exception.diagnostics["http_status"], 429)
        self.assertEqual(caught.exception.diagnostics["response_headers"]["Retry-After"], "7200")
        self.assertEqual(opener.request.get_header("User-agent"), USER_AGENT)
        sleeper.assert_called_once_with(60.0)


if __name__ == "__main__":
    unittest.main()
