import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from scripts.execute_target_text_corpus_v1_ready_channel_capture_v1 import execute
from scripts.verify_target_text_corpus_v1_ready_channel_capture_release_v1 import PASS_STATUS, verify


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "target_text_corpus_v1_ready_channel_capture_release_v1.json"
QA = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\ready_channel_wayback_capture_release_v1\independent_release_qa_v1.json")


class ReadyChannelCaptureReleaseV1Tests(unittest.TestCase):
    def test_real_release_passes_and_output_is_absent(self) -> None:
        result = verify(RELEASE)
        self.assertEqual(result["status"], PASS_STATUS, result["errors"])
        self.assertEqual(result["checks"]["record_count"], 53)
        self.assertTrue(result["checks"]["planned_output_absent"])

    def test_synthetic_execution_preserves_exact_order_without_live_access(self) -> None:
        payload = b"<html>" + b"x" * 2048 + b"</html>"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            def fake(url, contract, counter):
                counter[0] += 1
                return payload, url, 0, "text/html", {}
            report = execute(RELEASE, QA, datetime.fromisoformat("2026-10-28T16:00:00+07:00"), fetcher=fake, output_override=output)
        self.assertEqual(report["status"], "COMPLETE")
        self.assertEqual(report["network_request_count"], 53)
        self.assertEqual(report["captured_count"], 53)
        self.assertEqual(report["safety_contract"]["candidate_live_domain_access_operations"], 0)


if __name__ == "__main__":
    unittest.main()
