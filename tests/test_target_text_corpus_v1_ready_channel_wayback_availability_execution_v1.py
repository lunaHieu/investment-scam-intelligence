import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from scripts.execute_target_text_corpus_v1_ready_channel_wayback_availability_v1 import (
    AvailabilityRateLimitStop,
    _assert_archive_url,
    read_jsonl,
    run_plan,
)
from scripts.verify_target_text_corpus_v1_ready_channel_wayback_availability_execution_release_v1 import (
    PASS_STATUS,
    verify,
)


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "target_text_corpus_v1_ready_channel_wayback_availability_execution_release_v1.json"


class ReadyChannelWaybackAvailabilityExecutionV1Tests(unittest.TestCase):
    def test_real_release_is_exact_70_and_network_closed_at_freeze(self) -> None:
        result = verify(RELEASE)
        self.assertEqual(result["status"], PASS_STATUS, result["errors"])
        self.assertEqual(result["checks"]["plan_rows"], 70)
        self.assertEqual(result["checks"]["minimum_delay_seconds"], 60.0)
        self.assertEqual(result["checks"]["maximum_attempts_per_candidate"], 1)
        self.assertTrue(result["checks"]["partial_journal_required"])
        self.assertTrue(result["checks"]["dynamic_a1_report_gate_required"])
        self.assertFalse(result["checks"]["network_execution_allowed_now"])

    def test_archive_guard_rejects_candidate_host(self) -> None:
        with self.assertRaises(ValueError):
            _assert_archive_url("https://example.test/wayback/available", {"archive.org", "web.archive.org"}, "https://archive.org/wayback/available")

    def _fixture(self, directory: Path) -> tuple[dict, list[dict], Path, Path]:
        release = json.loads(RELEASE.read_text(encoding="utf-8"))
        plan = read_jsonl(Path(release["inputs"]["availability_plan"]["path"]))[:2]
        qa = directory / "qa.json"
        qa.write_text("{}\n", encoding="utf-8")
        output = directory / "result.json"
        return release, plan, qa, output

    def test_reservation_exists_before_fetch_and_success_finalizes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            release, plan, qa, output = self._fixture(root)
            partial = output.with_suffix(output.suffix + ".partial")

            def fetcher(url, contract, counter):
                self.assertTrue(partial.is_file())
                journal = json.loads(partial.read_text(encoding="utf-8"))
                self.assertEqual(journal["status"], "PARTIAL_DO_NOT_AUTO_RESUME")
                self.assertFalse(journal["resume_allowed"])
                counter[0] += 1
                return {"archived_snapshots": {}}, {"http_status": 200, "response_headers": {"Content-Type": "application/json"}}

            report = run_plan(RELEASE, qa, release, plan, output, datetime.now().astimezone().isoformat(), {"test": True}, fetcher=fetcher)
            self.assertTrue(output.is_file())
            self.assertFalse(partial.exists())
            self.assertEqual(report["status"], "COMPLETE")
            self.assertEqual(report["logical_attempt_count"], 2)
            self.assertEqual(report["network_request_count"], 2)
            self.assertEqual(report["unavailable_snapshot_count"], 2)

    def test_http_429_stops_remaining_rows_and_preserves_headers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            release, plan, qa, output = self._fixture(root)

            def fetcher(url, contract, counter):
                counter[0] += 1
                raise AvailabilityRateLimitStop("rate limited", {"http_status": 429, "response_headers": {"Retry-After": "3600", "Server": "nginx"}})

            report = run_plan(RELEASE, qa, release, plan, output, datetime.now().astimezone().isoformat(), {"test": True}, fetcher=fetcher)
            self.assertEqual(report["status"], "INCOMPLETE_ERRORS_PRESERVED")
            self.assertEqual(report["logical_attempt_count"], 1)
            self.assertEqual(report["network_request_count"], 1)
            self.assertTrue(report["stopped_on_http_429"])
            self.assertEqual(report["results"][0]["response_diagnostics"]["response_headers"]["Retry-After"], "3600")
            self.assertFalse(report["results"][1]["queried"])

    def test_process_crash_preserves_nonresumable_partial_journal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            release, plan, qa, output = self._fixture(root)
            partial = output.with_suffix(output.suffix + ".partial")

            def fetcher(url, contract, counter):
                self.assertTrue(partial.is_file())
                raise KeyboardInterrupt("synthetic process interruption")

            with self.assertRaises(KeyboardInterrupt):
                run_plan(RELEASE, qa, release, plan, output, datetime.now().astimezone().isoformat(), {"test": True}, fetcher=fetcher)
            self.assertFalse(output.exists())
            self.assertTrue(partial.is_file())
            journal = json.loads(partial.read_text(encoding="utf-8"))
            self.assertEqual(journal["status"], "PARTIAL_DO_NOT_AUTO_RESUME")
            self.assertFalse(journal["resume_allowed"])
            self.assertEqual(journal["network_request_count"], 0)


if __name__ == "__main__":
    unittest.main()
