import json
import tempfile
import unittest
import urllib.error
from datetime import datetime
from email.message import Message
from pathlib import Path
from unittest.mock import patch

from scripts.execute_sec_edgar_iapd_wayback_capture_v2 import execute
from scripts.verify_sec_edgar_iapd_wayback_capture_execution_amendment_v1 import verify
from scripts.verify_sec_edgar_iapd_wayback_capture_result_v1 import verify as verify_result
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file
from tests.test_sec_edgar_iapd_wayback_capture_release_v5 import (
    SecEdgarIapdWaybackCaptureReleaseV5Tests,
)


class SecEdgarIapdWaybackCaptureExecutionAmendmentV1Tests(unittest.TestCase):
    def make_amendment(self, directory: Path) -> tuple[Path, Path, Path, Path]:
        helper = SecEdgarIapdWaybackCaptureReleaseV5Tests()
        release_path, plan_path, report_path, _ = helper.make_release(directory)
        from scripts.verify_sec_edgar_iapd_wayback_capture_release_v5 import verify as verify_release

        release_qa = verify_release(release_path)
        release_qa_path = directory / "independent_release_qa_v5.json"
        release_qa_path.write_text(json.dumps(release_qa, indent=2) + "\n", encoding="utf-8")
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        amendment_qa_path = directory / "independent_execution_amendment_qa_v1.json"
        amendment = {
            "amendment_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_CAPTURE_EXECUTION_AMENDMENT_V1",
            "status": "FROZEN_DECOUPLED_CRASH_SAFE_CAPTURE_AUTHORIZATION",
            "basis": [],
            "inputs": {
                "capture_release_v5": {
                    "path": str(release_path),
                    "sha256": sha256_file(release_path),
                },
                "independent_release_qa_v5": {
                    "path": str(release_qa_path),
                    "sha256": sha256_file(release_qa_path),
                },
            },
            "execution_binding": {
                "capture_plan_rows": plan["planned_capture_count"],
                "capture_plan_by_cohort": plan["planned_by_cohort"],
                "authorized_executor_module": "scripts.execute_sec_edgar_iapd_wayback_capture_v2",
                "availability_v10_is_capture_prerequisite": False,
                "availability_requests_in_capture_process": 0,
                "same_process_after_availability_429_allowed": False,
                "original_v5_not_before_remains_binding": True,
                "reservation_before_first_request_required": True,
                "checkpoint_after_each_row_required": True,
                "automatic_partial_resume_allowed": False,
                "allowlisted_http_diagnostic_headers": [
                    "Retry-After",
                    "Date",
                    "Server",
                    "Content-Type",
                    "X-Archive-Wayback-Runtime-Error",
                ],
            },
            "independent_qa_output": {
                "path": str(amendment_qa_path),
                "verification_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_CAPTURE_EXECUTION_AMENDMENT_INDEPENDENT_QA_V1",
                "required_status": "PASS_DECOUPLED_CRASH_SAFE_CAPTURE_AMENDMENT",
            },
            "decision": {
                "archive_only_capture_allowed_under_v5_not_before": True,
                "candidate_live_domain_access_allowed": False,
                "text_extraction_allowed_before_complete_capture_qa": False,
                "labeling_allowed": False,
                "validation_or_test_opening_allowed": False,
                "training_allowed": False,
            },
        }
        amendment_path = directory / "capture_execution_amendment_v1.json"
        amendment_path.write_text(json.dumps(amendment, indent=2) + "\n", encoding="utf-8")
        checked = verify(amendment_path)
        amendment_qa_path.write_text(json.dumps(checked, indent=2) + "\n", encoding="utf-8")
        return amendment_path, release_path, release_qa_path, report_path

    def test_complete_capture_is_independent_of_v10_and_passes_existing_result_qa(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            amendment_path, release_path, release_qa_path, report_path = self.make_amendment(directory)

            def fake_fetch(url, *, timeout_seconds, delay_seconds, request_counter, max_redirects):
                self.assertTrue(url.startswith("https://web.archive.org/web/"))
                self.assertEqual(delay_seconds, 30.0)
                request_counter[0] += 1
                return b"<html>" + b"x" * 2048 + b"</html>", url, 0, "text/html"

            with patch(
                "scripts.execute_sec_edgar_iapd_wayback_capture_v2.fetch_archive",
                side_effect=fake_fetch,
            ):
                report = execute(
                    amendment_path,
                    now=datetime.fromisoformat("2026-10-21T22:30:00+07:00"),
                )
            self.assertEqual(report["status"], "COMPLETE")
            self.assertEqual(report["captured_count"], 2)
            self.assertEqual(report["executor"], "scripts.execute_sec_edgar_iapd_wayback_capture_v2")
            result_qa = verify_result(release_path, release_qa_path, report_path)
            self.assertEqual(
                result_qa["status"],
                "PASS_COMPLETE_TEXT_EXTRACTION_RELEASE_MAY_BE_PREPARED",
            )

    def test_checkpoint_is_preserved_when_process_stops(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            amendment_path, release_path, _, report_path = self.make_amendment(directory)

            def fake_fetch(url, *, timeout_seconds, delay_seconds, request_counter, max_redirects):
                request_counter[0] += 1
                return b"<html>" + b"x" * 2048 + b"</html>", url, 0, "text/html"

            with patch(
                "scripts.execute_sec_edgar_iapd_wayback_capture_v2.fetch_archive",
                side_effect=fake_fetch,
            ):
                with self.assertRaisesRegex(RuntimeError, "synthetic stop"):
                    execute(
                        amendment_path,
                        now=datetime.fromisoformat("2026-10-21T22:30:00+07:00"),
                        after_checkpoint=lambda _: (_ for _ in ()).throw(RuntimeError("synthetic stop")),
                    )
            partial = report_path.with_suffix(report_path.suffix + ".partial")
            self.assertTrue(partial.is_file())
            journal = json.loads(partial.read_text(encoding="utf-8"))
            self.assertEqual(len(journal["attempted_results"]), 1)
            self.assertEqual(len(journal["pending_availability_plan_ids"]), 1)
            self.assertFalse(journal["resume_allowed"])
            release = json.loads(release_path.read_text(encoding="utf-8"))
            plan = json.loads(Path(release["inputs"]["capture_plan"]["path"]).read_text(encoding="utf-8"))
            self.assertTrue(Path(plan["results"][0]["capture_path"]).is_file())

    def test_http_429_preserves_allowlisted_headers_and_stops(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            amendment_path, _, _, _ = self.make_amendment(directory)
            headers = Message()
            headers["Retry-After"] = "3600"
            headers["Server"] = "synthetic-wayback"
            headers["Set-Cookie"] = "must-not-be-recorded"

            def rate_limited(url, *, timeout_seconds, delay_seconds, request_counter, max_redirects):
                request_counter[0] += 1
                raise urllib.error.HTTPError(url, 429, "Too Many Requests", headers, None)

            with patch(
                "scripts.execute_sec_edgar_iapd_wayback_capture_v2.fetch_archive",
                side_effect=rate_limited,
            ):
                report = execute(
                    amendment_path,
                    now=datetime.fromisoformat("2026-10-21T22:30:00+07:00"),
                )
            self.assertTrue(report["stopped_on_http_429"])
            self.assertEqual(report["network_request_count"], 1)
            self.assertEqual(report["failed_count"], 1)
            self.assertEqual(report["not_attempted_count"], 1)
            diagnostic = report["results"][0]["diagnostic_response_headers"]
            self.assertEqual(diagnostic["Retry-After"], "3600")
            self.assertEqual(diagnostic["Server"], "synthetic-wayback")
            self.assertNotIn("Set-Cookie", diagnostic)


if __name__ == "__main__":
    unittest.main()
