import copy
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from scripts.execute_target_text_corpus_v1_ready_channel_cdx_bulk_v1 import execute
from scripts.verify_target_text_corpus_v1_ready_channel_cdx_bulk_release_v1 import PASS_STATUS, target_rows, verify


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "target_text_corpus_v1_ready_channel_cdx_bulk_release_v1.json"
QA = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\ready_channel_wayback_availability_plan_v1\independent_cdx_bulk_release_qa_v1.json")


class ReadyChannelCdxBulkV1Tests(unittest.TestCase):
    def test_real_release_is_exact_unresolved_only_and_verified(self) -> None:
        result = verify(RELEASE)
        self.assertEqual(result["status"], PASS_STATUS, result["errors"])
        rows = target_rows(RELEASE)
        self.assertEqual(len(rows), 68)
        self.assertEqual(rows[0]["availability_plan_id"], "TTCV1_B3_AVAIL_003")
        self.assertEqual(rows[-1]["availability_plan_id"], "TTCV1_B3_AVAIL_070")

    def test_reincluding_canary_row_fails_closed(self) -> None:
        value = json.loads(RELEASE.read_text(encoding="utf-8"))
        value["population_contract"]["excluded_availability_plan_ids"] = ["TTCV1_B3_AVAIL_001"]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", dir=ROOT / "configs", encoding="utf-8", delete=False) as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            path = Path(handle.name)
        try:
            result = verify(path, require_output_absent=False)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("exclusions" in error for error in result["errors"]))

    def test_synthetic_exact_68_execution_preserves_order_without_page_download(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output, raw = root / "report.json", root / "raw"

            def fetcher(url, contract, counter):
                counter[0] += 1
                return b"[]", {"http_status": 200, "content_type": "application/json", "response_bytes": 2, "response_sha256": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e4f17f4e3f1f4d69f61d2a2", "response_headers": {}}

            report = execute(RELEASE, QA, datetime.fromisoformat("2026-10-28T10:00:00+07:00"), fetcher=fetcher, output_override=output, raw_dir_override=raw)
        self.assertEqual(report["status"], "COMPLETE_EXACT_68_CDX_METADATA")
        self.assertEqual(report["network_request_count"], 68)
        self.assertEqual(report["results"][0]["availability_plan_id"], "TTCV1_B3_AVAIL_003")
        self.assertEqual(report["results"][-1]["availability_plan_id"], "TTCV1_B3_AVAIL_070")
        self.assertEqual(report["safety_contract"]["archived_page_download_operations"], 0)


if __name__ == "__main__":
    unittest.main()
