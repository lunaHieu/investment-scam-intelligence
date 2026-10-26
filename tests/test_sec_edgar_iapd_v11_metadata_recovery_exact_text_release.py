import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_sec_edgar_iapd_v11_metadata_recovery_exact_text_release import build_release


class V11MetadataRecoveryExactTextReleaseTests(unittest.TestCase):
    def test_metadata_recovery_qa_gate_blocks_before_capture_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            capture = root / "capture.json"
            capture.write_text(json.dumps({"status": "RECONCILED_CAPTURED_BYTES_METADATA_INCOMPLETE", "results": []}), encoding="utf-8")
            qa = root / "qa.json"
            qa.write_text(json.dumps({"status": "PASS_REPAIRED_RAW_BYTES_METADATA_INCOMPLETE_EXTRACTION_CLOSED", "decision": {"text_extraction_release_may_be_prepared": False}, "inputs": {"report_sha256": "wrong"}}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "blocked"):
                build_release(capture_report_path=capture, capture_qa_path=qa, text_root=root / "text", manifest_path=root / "manifest.jsonl", report_path=root / "report.json", created_at="2026-10-26T00:00:00+07:00")


if __name__ == "__main__":
    unittest.main()
