import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from scripts.build_sec_edgar_iapd_wayback_capture_plan_v1 import build_plan
from scripts.build_sec_edgar_iapd_wayback_capture_release_v1 import build_release
from scripts.execute_sec_edgar_iapd_wayback_capture_v1 import execute
from scripts.verify_sec_edgar_iapd_wayback_capture_release_v1 import verify
from scripts.verify_sec_edgar_iapd_wayback_capture_result_v1 import verify as verify_result
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file
from tests.test_sec_edgar_iapd_wayback_capture_plan_v1 import RELEASE, write_fixture


class SecEdgarIapdWaybackCaptureReleaseV1Tests(unittest.TestCase):
    def make_release(self, directory: Path) -> tuple[Path, Path, Path]:
        availability_path, availability_qa_path = write_fixture(directory)
        plan = build_plan(
            release_path=RELEASE,
            availability_path=availability_path,
            qa_path=availability_qa_path,
            raw_root=directory / "raw",
            capture_date="2026-10-14",
        )
        plan_path = directory / "capture_plan.json"
        plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        plan_qa = {
            "status": "PASS_EXACT_AVAILABLE_SNAPSHOT_PLAN_REGISTER_BEFORE_EXECUTION",
            "plan": {"path": str(plan_path), "sha256": sha256_file(plan_path)},
            "decision": {"capture_execution_release_may_be_prepared": True},
            "errors": [],
        }
        plan_qa_path = directory / "capture_plan_qa.json"
        plan_qa_path.write_text(json.dumps(plan_qa, indent=2) + "\n", encoding="utf-8")
        report_path = directory / "capture_report.json"
        release = build_release(
            plan_path=plan_path,
            qa_path=plan_qa_path,
            not_before="2026-10-14T01:00:00+07:00",
            report_path=report_path,
            created_at="2026-10-14T00:59:00+07:00",
        )
        release_path = directory / "capture_release.json"
        release_path.write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
        release_qa = verify(release_path)
        release_qa_path = directory / "capture_release_qa.json"
        release_qa_path.write_text(json.dumps(release_qa, indent=2) + "\n", encoding="utf-8")
        return release_path, release_qa_path, report_path

    def test_release_verifier_passes_and_keeps_text_extraction_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            release_path, _, _ = self.make_release(Path(tmp))
            result = verify(release_path)
        self.assertEqual(result["status"], "PASS_ARCHIVE_ONLY_CAPTURE_RELEASE")
        self.assertEqual(result["checks"]["minimum_delay_seconds"], 30.0)
        self.assertFalse(result["decision"]["text_extraction_allowed"])

    def test_executor_captures_only_frozen_archive_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            release_path, release_qa_path, report_path = self.make_release(directory)

            def fake_fetch(url, *, timeout_seconds, delay_seconds, request_counter, max_redirects):
                self.assertTrue(url.startswith("https://web.archive.org/web/"))
                self.assertIn("id_/", url)
                self.assertEqual(delay_seconds, 30.0)
                request_counter[0] += 1
                return b"<html>" + b"x" * 2048 + b"</html>", url, 0, "text/html"

            with patch("scripts.execute_sec_edgar_iapd_wayback_capture_v1.fetch_archive", side_effect=fake_fetch):
                report = execute(
                    release_path,
                    release_qa_path,
                    now=datetime.fromisoformat("2026-10-14T01:00:00+07:00"),
                )
            self.assertTrue(report_path.exists())
            self.assertEqual(report["status"], "COMPLETE")
            self.assertEqual(report["captured_count"], 2)
            self.assertEqual(report["network_request_count"], 2)
            self.assertEqual(report["captured_by_cohort"], {"DEVELOPMENT": 1, "EXTERNAL_HOLDOUT": 1})
            self.assertTrue(all(Path(row["capture_path"]).exists() for row in report["results"]))
            result_qa = verify_result(release_path, release_qa_path, report_path)
            self.assertEqual(result_qa["status"], "PASS_COMPLETE_TEXT_EXTRACTION_RELEASE_MAY_BE_PREPARED")
            self.assertTrue(result_qa["decision"]["text_extraction_release_may_be_prepared"])

    def test_executor_refuses_before_not_before(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            release_path, release_qa_path, _ = self.make_release(Path(tmp))
            with self.assertRaisesRegex(PermissionError, "not-before gate"):
                execute(
                    release_path,
                    release_qa_path,
                    now=datetime.fromisoformat("2026-10-14T00:59:59+07:00"),
                )

    def test_result_verifier_detects_raw_byte_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            release_path, release_qa_path, report_path = self.make_release(directory)

            def fake_fetch(url, *, timeout_seconds, delay_seconds, request_counter, max_redirects):
                request_counter[0] += 1
                return b"<html>" + b"x" * 2048 + b"</html>", url, 0, "text/html"

            with patch("scripts.execute_sec_edgar_iapd_wayback_capture_v1.fetch_archive", side_effect=fake_fetch):
                report = execute(
                    release_path,
                    release_qa_path,
                    now=datetime.fromisoformat("2026-10-14T01:00:00+07:00"),
                )
            target = Path(report["results"][0]["capture_path"])
            target.write_bytes(target.read_bytes() + b"tamper")
            result_qa = verify_result(release_path, release_qa_path, report_path)
            self.assertEqual(result_qa["status"], "FAIL")
            self.assertTrue(any("byte/hash mismatch" in error for error in result_qa["errors"]))


if __name__ == "__main__":
    unittest.main()
