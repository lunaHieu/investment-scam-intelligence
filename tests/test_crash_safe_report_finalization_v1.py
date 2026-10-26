import json
import tempfile
import unittest
from pathlib import Path

from scripts.crash_safe_report_finalization_v1 import finalize_reserved_report, promote_verified_complete_partial


class CrashSafeReportFinalizationV1Tests(unittest.TestCase):
    def test_success_atomically_removes_partial(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / "report.json"
            partial = report.with_suffix(".json.partial")
            partial.write_text(json.dumps({"status": "RESERVED_BEFORE_NETWORK_NON_RESUMABLE"}), encoding="utf-8")
            value = {"status": "COMPLETE", "results": [{"outcome": "CAPTURED"}]}
            finalize_reserved_report(report, value)
            self.assertEqual(json.loads(report.read_text(encoding="utf-8")), value)
            self.assertFalse(partial.exists())
            self.assertFalse(report.with_suffix(".json.finalizing").exists())

    def test_complete_partial_can_be_promoted_offline(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / "report.json"
            partial = report.with_suffix(".json.partial")
            value = {"status": "INCOMPLETE_FAILURES_PRESERVED", "results": []}
            partial.write_text(json.dumps(value), encoding="utf-8")
            promote_verified_complete_partial(report)
            self.assertEqual(json.loads(report.read_text(encoding="utf-8")), value)
            self.assertFalse(partial.exists())

    def test_reservation_cannot_be_promoted_as_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / "report.json"
            report.with_suffix(".json.partial").write_text(json.dumps({"status": "RESERVED_BEFORE_NETWORK_NON_RESUMABLE"}), encoding="utf-8")
            with self.assertRaises(ValueError):
                promote_verified_complete_partial(report)


if __name__ == "__main__":
    unittest.main()
