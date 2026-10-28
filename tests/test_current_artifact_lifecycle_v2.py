import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_ready_channel_cdx_canary_release_v1 import PASS_STATUS, verify
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "target_text_corpus_v1_ready_channel_cdx_canary_release_v1.json"
REPORT = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\ready_channel_cdx_canary_result_v1\cdx_canary_report_v1.json")
QA = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\ready_channel_cdx_canary_result_v1\independent_result_qa_v1.json")


class CurrentArtifactLifecycleV2Tests(unittest.TestCase):
    def test_consumed_canary_release_and_result_verify(self) -> None:
        result = verify(RELEASE, require_output_absent=False)
        self.assertEqual(result["status"], PASS_STATUS, result["errors"])
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        qa = json.loads(QA.read_text(encoding="utf-8"))
        self.assertEqual(sha256_file(REPORT), "0a139703b6d259fd115f2434653223b6fd4f91dace6629f8740ca32731143235")
        self.assertEqual(sha256_file(QA), "2a4774f363d0684cdbe2f27eedc809045277615f06adf2a862dae8d929a46827")
        self.assertEqual(report["status"], "COMPLETE_VALID_CDX_CANARY_WITH_ELIGIBLE_METADATA")
        self.assertEqual(qa["status"], "PASS_CDX_CANARY_VALID_BULK_RELEASE_MAY_BE_PREPARED")
        self.assertFalse(qa["decision"]["capture_authorized"])


if __name__ == "__main__":
    unittest.main()
