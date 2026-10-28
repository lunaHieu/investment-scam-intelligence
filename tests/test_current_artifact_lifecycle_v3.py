import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_ready_channel_cdx_bulk_release_v1 import PASS_STATUS, verify
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "target_text_corpus_v1_ready_channel_cdx_bulk_release_v1.json"
REPORT = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\ready_channel_cdx_bulk_result_v1\cdx_bulk_report_v1.json")
QA = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\ready_channel_cdx_bulk_result_v1\independent_result_qa_v1.json")


class CurrentArtifactLifecycleV3Tests(unittest.TestCase):
    def test_consumed_bulk_release_and_result_verify(self) -> None:
        result = verify(RELEASE, require_output_absent=False)
        self.assertEqual(result["status"], PASS_STATUS, result["errors"])
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        qa = json.loads(QA.read_text(encoding="utf-8"))
        self.assertEqual(sha256_file(REPORT), "dbeaa62e7b03e63c8b50a514cdf29363e684a55fcfbfcd7e0c5feeb60d7bb105")
        self.assertEqual(sha256_file(QA), "cc2db264066e5e235bad5547d63331186ef476a8fe71951f403a1d0df265bb00")
        self.assertEqual(report["status"], "COMPLETE_EXACT_68_CDX_METADATA")
        self.assertEqual(qa["status"], "PASS_COMPLETE_EXACT_68_CDX_METADATA_CAPTURE_PLAN_MAY_BE_PREPARED")
        self.assertFalse(qa["decision"]["capture_authorized"])


if __name__ == "__main__":
    unittest.main()
