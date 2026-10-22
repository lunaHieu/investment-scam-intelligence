import json
import tempfile
import unittest
import urllib.error
from copy import deepcopy
from datetime import datetime
from email.message import Message
from pathlib import Path
from unittest.mock import patch

from scripts.retry_sec_edgar_iapd_wayback_availability_v11 import (
    AvailabilityRateLimitStop,
    USER_AGENT,
    execute,
    fetch_availability,
    request_url,
)


MODULE = "scripts.retry_sec_edgar_iapd_wayback_availability_v11"


def row(identifier: str, error: str | None, cohort: str = "EXTERNAL_HOLDOUT") -> dict:
    return {
        "availability_plan_id": identifier,
        "shortlist_id": "SHORT-" + identifier,
        "cohort": cohort,
        "candidate_host": identifier + ".example",
        "candidate_url": "https://" + identifier + ".example/",
        "query_timestamp": "20261003",
        "queried": error is None,
        "available": False if error is None else None,
        "snapshot_timestamp": None,
        "snapshot_url": None,
        "snapshot_http_status": None,
        "error": error,
    }


class _RateLimitedOpener:
    def __init__(self) -> None:
        self.request = None

    def open(self, request, timeout):
        self.request = request
        headers = Message()
        headers["Retry-After"] = "3600"
        headers["Date"] = "Fri, 23 Oct 2026 17:00:00 GMT"
        headers["Server"] = "nginx"
        headers["X-Archive-Wayback-Runtime-Error"] = "rate limit"
        raise urllib.error.HTTPError(request.full_url, 429, "Too Many Requests", headers, None)


class AvailabilityV11ExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.output = root / "availability_report_v11.json"
        self.release_path = root / "release.json"
        self.release_qa_path = root / "qa.json"
        self.release_path.write_text("{}\n", encoding="utf-8")
        self.release_qa_path.write_text("{}\n", encoding="utf-8")
        self.retry_rows = [row("retry-a", "old-a"), row("retry-b", "old-b")]
        self.release = {
            "release_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_RELEASE_V11",
            "cooldown_contract": {"not_before": "2026-10-25T00:00:00+07:00"},
            "ordered_retry_rows": [
                {key: value for key, value in item.items() if key in {
                    "availability_plan_id", "shortlist_id", "cohort", "candidate_host",
                    "candidate_url", "query_timestamp"
                }}
                for item in self.retry_rows
            ],
            "network_contract": {
                "endpoint": "https://archive.org/wayback/available",
                "allowed_network_hosts": ["archive.org", "web.archive.org"],
                "minimum_delay_seconds": 60.0,
                "timeout_seconds": 30,
                "maximum_redirects": 3,
                "maximum_response_bytes": 2097152,
            },
            "planned_output": {
                "path": str(self.output),
                "report_id": "ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_AVAILABILITY_REPORT_V11",
            },
        }
        resolved = [row(f"resolved-{index}", None, "DEVELOPMENT") for index in range(113)]
        self.parent = {
            "cumulative_network_request_count": 168,
            "results": resolved + deepcopy(self.retry_rows),
        }
        self.protocol = {
            "inputs": {
                "availability_report_v10": {"path": "parent.json", "sha256": "a" * 64}
            }
        }
        self.now = datetime.fromisoformat("2026-10-25T00:00:00+07:00")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _inputs_patch(self):
        return patch(
            MODULE + ".validate_inputs",
            return_value=(deepcopy(self.release), deepcopy(self.protocol), deepcopy(self.parent)),
        )

    @staticmethod
    def _success(_url, _contract, counter):
        counter[0] += 1
        return {"archived_snapshots": {}}, {
            "http_status": 200,
            "response_headers": {"Content-Type": "application/json"},
        }

    def test_pre_gate_fails_before_reserving_output(self) -> None:
        with self._inputs_patch():
            with self.assertRaises(PermissionError):
                execute(
                    self.release_path,
                    self.release_qa_path,
                    datetime.fromisoformat("2026-10-24T23:59:59+07:00"),
                )
        self.assertFalse(self.output.exists())

    def test_http_429_preserves_required_headers(self) -> None:
        contract = self.release["network_contract"]
        counter = [0]
        opener = _RateLimitedOpener()
        with patch(MODULE + ".urllib.request.build_opener", return_value=opener), patch(
            MODULE + ".time.sleep"
        ) as sleeper:
            with self.assertRaises(AvailabilityRateLimitStop) as caught:
                fetch_availability(
                    request_url(contract["endpoint"], "https://example.test/", "20261003"),
                    contract,
                    counter,
                )
        self.assertEqual(counter, [1])
        headers = caught.exception.diagnostics["response_headers"]
        self.assertEqual(headers["Retry-After"], "3600")
        self.assertEqual(headers["X-Archive-Wayback-Runtime-Error"], "rate limit")
        self.assertEqual(opener.request.get_header("User-agent"), USER_AGENT)
        sleeper.assert_called_once_with(60.0)

    def test_crash_checkpoint_is_non_resumable(self) -> None:
        def crash(_checkpoint):
            raise RuntimeError("simulated crash")

        with self._inputs_patch():
            with self.assertRaisesRegex(RuntimeError, "simulated crash"):
                execute(
                    self.release_path,
                    self.release_qa_path,
                    self.now,
                    fetcher=self._success,
                    after_checkpoint=crash,
                )
        partial = self.output.with_suffix(self.output.suffix + ".partial")
        journal = json.loads(partial.read_text(encoding="utf-8"))
        self.assertEqual(journal["status"], "PARTIAL_DO_NOT_AUTO_RESUME")
        self.assertFalse(journal["resume_allowed"])
        self.assertEqual(journal["attempted_availability_plan_ids"], ["retry-a"])
        self.assertEqual(journal["pending_availability_plan_ids"], ["retry-b"])

    def test_happy_path_preserves_113_rows_and_resolves_exact_two(self) -> None:
        with self._inputs_patch():
            report = execute(
                self.release_path,
                self.release_qa_path,
                self.now,
                fetcher=self._success,
            )
        self.assertEqual(report["status"], "COMPLETE")
        self.assertEqual(report["resolved_results_reused_from_v10"], 113)
        self.assertEqual(report["retried_availability_plan_ids"], ["retry-a", "retry-b"])
        self.assertEqual(report["logical_retry_attempt_count"], 2)
        self.assertEqual(report["network_request_count_this_attempt"], 2)
        self.assertTrue(report["supplemental_availability_complete"])
        self.assertFalse(report["original_capture_plan_mutation_allowed"])


if __name__ == "__main__":
    unittest.main()
