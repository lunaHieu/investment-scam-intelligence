import tempfile
import unittest
import urllib.error
from email.message import Message
from pathlib import Path
from unittest.mock import patch

from scripts.execute_sec_edgar_iapd_wayback_capture_retry_v2 import (
    REQUEST_HEADERS,
    USER_AGENT,
    capture_row,
    execute,
)


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "sec_edgar_iapd_wayback_capture_missing_row_retry_release_v1.json"
RELEASE_QA = Path(
    r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\sec_edgar_iapd_all_filer_wayback_capture_retry_result_v1\independent_release_qa_v1.json"
)


def row_for(path: Path) -> dict:
    return {
        "availability_plan_id": "retry-1",
        "shortlist_id": "short-1",
        "cohort": "DEVELOPMENT",
        "candidate_host": "example.test",
        "candidate_url": "https://example.test/",
        "snapshot_timestamp": "20260101000000",
        "snapshot_url": "https://web.archive.org/web/20260101000000/https://example.test/",
        "requested_archive_url": "https://web.archive.org/web/20260101000000id_/https://example.test/",
        "capture_path": str(path),
    }


class _RateLimitedOpener:
    def __init__(self) -> None:
        self.request = None

    def open(self, request, timeout):
        self.request = request
        headers = Message()
        headers["Retry-After"] = "3600"
        headers["Server"] = "nginx"
        raise urllib.error.HTTPError(request.full_url, 429, "Too Many Requests", headers, None)


class SecEdgarIapdWaybackCaptureRetryExecutionV2Tests(unittest.TestCase):
    def test_user_agent_satisfies_current_archive_identification_policy(self) -> None:
        self.assertIn("ISI-Research/2.0", USER_AGENT)
        self.assertIn("gpt-5", USER_AGENT)
        self.assertIn("github.com/lunaHieu/investment-scam-intelligence", USER_AGENT)
        self.assertEqual(REQUEST_HEADERS["User-Agent"], USER_AGENT)

    def test_http_429_preserves_retry_after_and_stops_without_raw_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "capture.html"
            opener = _RateLimitedOpener()
            contract = {
                "minimum_delay_seconds": 30.0,
                "timeout_seconds": 30,
                "maximum_redirects": 3,
                "maximum_response_bytes": 1024 * 1024,
                "required_content_type_prefix": "text/html",
            }
            with patch(
                "scripts.execute_sec_edgar_iapd_wayback_capture_retry_v2.urllib.request.build_opener",
                return_value=opener,
            ), patch(
                "scripts.execute_sec_edgar_iapd_wayback_capture_retry_v2.time.sleep"
            ) as sleeper:
                result, requests = capture_row(row_for(target), contract)

            self.assertEqual(requests, 1)
            self.assertEqual(result["outcome"], "FAILED")
            self.assertEqual(result["http_status"], 429)
            self.assertEqual(
                result["response_diagnostics"]["response_headers"]["Retry-After"],
                "3600",
            )
            self.assertFalse(target.exists())
            self.assertEqual(opener.request.get_header("User-agent"), USER_AGENT)
            sleeper.assert_called_once_with(30.0)

    def test_real_release_still_fails_closed_before_original_gate(self) -> None:
        from datetime import datetime

        import json

        release = json.loads(RELEASE.read_text(encoding="utf-8"))
        output = Path(release["planned_output"]["path"])
        expected = "independent recomputation failed" if output.exists() else "not-before gate is closed"
        with self.assertRaisesRegex(PermissionError, expected):
            execute(RELEASE, RELEASE_QA, datetime.fromisoformat("2026-10-22T23:00:00+07:00"))


if __name__ == "__main__":
    unittest.main()
