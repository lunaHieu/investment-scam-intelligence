import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from scripts.build_sec_edgar_iapd_exact_text_release_v1 import build_release
from scripts.execute_sec_edgar_iapd_wayback_capture_v1 import execute as execute_capture
from scripts.extract_sec_edgar_iapd_exact_text_v1 import execute as execute_extraction
from scripts.verify_sec_edgar_iapd_exact_text_release_v1 import verify as verify_release
from scripts.verify_sec_edgar_iapd_exact_text_result_v1 import verify as verify_result
from scripts.verify_sec_edgar_iapd_wayback_capture_result_v1 import verify as verify_capture
from tests import test_sec_edgar_iapd_wayback_capture_release_v1 as capture_helpers


class SecEdgarIapdExactTextV1Tests(unittest.TestCase):
    def make_release(self, directory: Path) -> tuple[Path, Path, dict]:
        helper = capture_helpers.SecEdgarIapdWaybackCaptureReleaseV1Tests()
        capture_release, capture_release_qa, capture_report = helper.make_release(directory)

        def fake_fetch(url, *, timeout_seconds, delay_seconds, request_counter, max_redirects):
            request_counter[0] += 1
            payload = b"<html><head><title>Reference page</title></head><body>Independent adviser profile and investment services.</body></html>"
            return payload, url, 0, "text/html"

        with patch("scripts.execute_sec_edgar_iapd_wayback_capture_v1.fetch_archive", side_effect=fake_fetch):
            execute_capture(capture_release, capture_release_qa, now=datetime.fromisoformat("2026-10-14T01:00:00+07:00"))
        capture_qa = verify_capture(capture_release, capture_release_qa, capture_report)
        capture_qa_path = directory / "capture_result_qa.json"
        capture_qa_path.write_text(json.dumps(capture_qa, indent=2) + "\n", encoding="utf-8")
        output_root = directory / "exact_text"
        release = build_release(
            capture_report_path=capture_report,
            capture_qa_path=capture_qa_path,
            text_root=output_root / "text",
            manifest_path=output_root / "manifest.jsonl",
            report_path=output_root / "report.json",
            created_at="2026-10-14T01:10:00+07:00",
        )
        release_path = directory / "exact_text_release.json"
        release_path.write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
        release_qa = verify_release(release_path)
        release_qa_path = directory / "exact_text_release_qa.json"
        release_qa_path.write_text(json.dumps(release_qa, indent=2) + "\n", encoding="utf-8")
        return release_path, release_qa_path, release

    def test_release_and_offline_extraction_verify_byte_for_byte(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            release_path, release_qa_path, release = self.make_release(Path(tmp))
            self.assertEqual(verify_release(release_path)["status"], "PASS_OFFLINE_EXACT_TEXT_RELEASE")
            report = execute_extraction(release_path, release_qa_path)
            self.assertEqual(report["counts"]["extracted_count"], 2)
            self.assertEqual(report["counts"]["minimum_content_passed_count"], 2)
            result = verify_result(release_path, release_qa_path)
            self.assertEqual(result["status"], "PASS_EXACT_TEXT_BYTES_REGENERATED_GROUPING_MAY_BE_PREPARED")
            self.assertEqual(result["checks"]["byte_for_byte_match_count"], 2)
            self.assertFalse(result["decision"]["human_label_review_allowed"])
            self.assertTrue(Path(release["outputs"]["manifest"]).is_file())

    def test_extraction_refuses_to_overwrite_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            release_path, release_qa_path, _ = self.make_release(Path(tmp))
            execute_extraction(release_path, release_qa_path)
            with self.assertRaises(FileExistsError):
                execute_extraction(release_path, release_qa_path)


if __name__ == "__main__":
    unittest.main()
