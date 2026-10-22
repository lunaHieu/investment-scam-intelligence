import hashlib
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from scripts.execute_sec_edgar_iapd_wayback_capture_retry_v1 import (
    ResponseValidationError,
    capture_row,
    execute,
)
from scripts.verify_sec_edgar_iapd_wayback_capture_retry_result_v1 import verify
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "sec_edgar_iapd_wayback_capture_missing_row_retry_release_v1.json"
RELEASE_QA = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\sec_edgar_iapd_all_filer_wayback_capture_retry_result_v1\independent_release_qa_v1.json")


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


class SecEdgarIapdWaybackCaptureRetryExecutionV1Tests(unittest.TestCase):
    def test_success_writes_exact_bytes_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "capture.html"
            payload = b"x" * 1024

            def fetcher(url, contract, counter):
                counter[0] += 1
                return payload, {"final_archive_url": url, "redirect_count": 0, "http_status": 200, "content_type": "text/html", "response_bytes": len(payload), "response_sha256": hashlib.sha256(payload).hexdigest(), "response_headers": {}}

            result, requests = capture_row(row_for(target), {}, fetcher)
            self.assertEqual(requests, 1)
            self.assertEqual(result["outcome"], "CAPTURED")
            self.assertEqual(target.read_bytes(), payload)
            self.assertEqual(result["sha256"], hashlib.sha256(payload).hexdigest())

    def test_below_minimum_preserves_diagnostics_without_raw_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "capture.html"
            payload = b"short"
            diagnostics = {"final_archive_url": "https://web.archive.org/", "redirect_count": 0, "http_status": 200, "content_type": "text/html", "response_bytes": len(payload), "response_sha256": hashlib.sha256(payload).hexdigest(), "response_headers": {"Content-Type": "text/html"}}

            def fetcher(url, contract, counter):
                counter[0] += 1
                raise ResponseValidationError("Archived HTML capture is unexpectedly small: 5 bytes", diagnostics)

            result, requests = capture_row(row_for(target), {}, fetcher)
            self.assertEqual(requests, 1)
            self.assertEqual(result["outcome"], "FAILED")
            self.assertFalse(target.exists())
            self.assertEqual(result["response_diagnostics"]["response_sha256"], hashlib.sha256(payload).hexdigest())

    def test_real_release_gate_is_closed_before_not_before(self) -> None:
        with self.assertRaisesRegex(PermissionError, "not-before gate is closed"):
            execute(RELEASE, RELEASE_QA, datetime.fromisoformat("2026-10-22T23:00:00+07:00"))

    def test_failure_result_verifier_keeps_quarantine(self) -> None:
        release = json.loads(RELEASE.read_text(encoding="utf-8"))
        source = release["retry_rows"][0]
        self.assertFalse(Path(source["capture_path"]).exists())
        diagnostics = {"response_bytes": 42, "response_sha256": "0" * 64, "http_status": 200, "content_type": "text/html"}
        result = {key: source[key] for key in ("availability_plan_id", "shortlist_id", "cohort", "candidate_host", "candidate_url", "snapshot_timestamp", "snapshot_url", "requested_archive_url", "capture_path")}
        result.update({"outcome": "FAILED", "http_status": 200, "bytes": None, "sha256": None, "response_diagnostics": diagnostics, "error": "ResponseValidationError: Archived HTML capture is unexpectedly small: 42 bytes"})
        report = {"release_sha256": sha256_file(RELEASE), "release_qa_sha256": sha256_file(RELEASE_QA), "captured_count": 0, "failed_count": 1, "results": [result]}
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.json"
            report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            qa = verify(RELEASE, RELEASE_QA, report_path)
        self.assertEqual(qa["status"], "PASS_RETRY_FAILURE_PRESERVED_QUARANTINE_REMAINS")
        self.assertFalse(qa["decision"]["supplemental_pipeline_may_be_prepared"])


if __name__ == "__main__":
    unittest.main()
