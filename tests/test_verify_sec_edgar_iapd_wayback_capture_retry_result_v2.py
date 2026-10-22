import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_sec_edgar_iapd_wayback_capture_retry_result_v2 import verify


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "sec_edgar_iapd_wayback_capture_missing_row_retry_release_v1.json"
DATA = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\sec_edgar_iapd_all_filer_wayback_capture_retry_result_v1")
RELEASE_QA = DATA / "independent_release_qa_v1.json"
REPORT = DATA / "capture_retry_report_v1.json"


class VerifySecEdgarIapdWaybackCaptureRetryResultV2Tests(unittest.TestCase):
    def test_real_failure_report_passes_and_keeps_quarantine(self) -> None:
        result = verify(RELEASE, RELEASE_QA, REPORT)
        self.assertEqual(result["status"], "PASS_RETRY_FAILURE_PRESERVED_QUARANTINE_REMAINS")
        self.assertEqual(result["errors"], [])
        self.assertTrue(result["checks"]["completed_capture_ledger_preserved"])
        self.assertEqual(result["checks"]["http_status"], 200)
        self.assertEqual(result["checks"]["response_bytes"], 42)
        self.assertTrue(result["decision"]["quarantine_remains"])
        self.assertFalse(result["decision"]["another_retry_allowed_by_this_qa"])

    def test_missing_diagnostics_fails(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        changed = copy.deepcopy(report)
        changed["results"][0]["response_diagnostics"] = {}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            path.write_text(json.dumps(changed, indent=2) + "\n", encoding="utf-8")
            result = verify(RELEASE, RELEASE_QA, path)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("Failed retry lacks complete response diagnostics", result["errors"])


if __name__ == "__main__":
    unittest.main()
