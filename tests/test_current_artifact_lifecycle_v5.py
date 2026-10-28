import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_ready_channel_capture_continuation_release_v2 import sha


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "target_text_corpus_v1_ready_channel_capture_continuation_release_v1.json"
REPORT = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\ready_channel_wayback_capture_continuation_result_v1\capture_report_continuation_v1.json")
QA = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\ready_channel_wayback_capture_continuation_result_v1\independent_result_qa_v1.json")


class CurrentArtifactLifecycleV5Tests(unittest.TestCase):
    def test_consumed_exact_49_continuation_and_partial_result_verify(self):
        release = json.loads(RELEASE.read_text(encoding="utf-8"))
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        qa = json.loads(QA.read_text(encoding="utf-8"))
        self.assertEqual(sha(RELEASE), "364e952a21e1d61d2fdf70d59a768fd5527a4d33acae98df0581679c5c18daac")
        self.assertEqual(release["identity_contract"]["record_count"], 49)
        self.assertEqual(sha(REPORT), "d4e94a239535f96f3f51f4f63b6adffaf31f120a2beb97cbc2d912fbba741b25")
        self.assertEqual(sha(QA), "24be6216cf73921f5fb1707df338b090bc39b26fcdc1f6ba5fe9e8493ff629b5")
        self.assertEqual(report["captured_count"], 0)
        self.assertEqual(report["failed_count"], 1)
        self.assertEqual(report["not_attempted_count"], 48)
        self.assertEqual(qa["status"], "PASS_PARTIAL_CONTINUATION_PRESERVED")
        self.assertFalse(qa["decision"]["automatic_retry_allowed"])


if __name__ == "__main__":
    unittest.main()
