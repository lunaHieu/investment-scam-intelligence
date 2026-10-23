import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_sec_edgar_iapd_wayback_alternate_snapshot_cdx_owner_override_result_v1 import verify as verify_v1
from scripts.verify_sec_edgar_iapd_wayback_alternate_snapshot_cdx_owner_override_result_v2 import CANONICAL_EMPTY_SHA256, PASS_STATUS, verify


ROOT = Path(__file__).resolve().parents[1]
BASE = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\sec_edgar_iapd_alternate_snapshot_cdx_v1")
OVERRIDE = ROOT / "configs" / "sec_edgar_iapd_wayback_alternate_snapshot_cdx_owner_timing_override_v1.json"
OVERRIDE_QA = BASE / "independent_owner_timing_override_qa_v1.json"
REPORT = BASE / "cdx_enumeration_report_v1.json"
V1_QA = BASE / "independent_result_qa_owner_override_v1.json"


class AlternateSnapshotCdxOwnerOverrideResultV2Tests(unittest.TestCase):
    def test_real_three_byte_empty_response_closes_a1_without_retry(self):
        result = verify(OVERRIDE, OVERRIDE_QA, REPORT, V1_QA)
        self.assertEqual(result["status"], PASS_STATUS)
        self.assertEqual(result["checks"]["canonical_empty_payload_sha256_recomputed"], CANONICAL_EMPTY_SHA256)
        self.assertTrue(result["decision"]["a1_complete"])
        self.assertFalse(result["decision"]["same_query_retry_allowed"])

    def test_noncanonical_hash_is_rejected(self):
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        report["response_diagnostics"]["response_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.json"
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            v1 = verify_v1(OVERRIDE, OVERRIDE_QA, report_path, require_frozen_output_path=False)
            v1_path = Path(tmp) / "v1.json"
            v1_path.write_text(json.dumps(v1, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            result = verify(OVERRIDE, OVERRIDE_QA, report_path, v1_path, require_frozen_output_path=False)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("canonical empty" in error for error in result["errors"]))


if __name__ == "__main__": unittest.main()
