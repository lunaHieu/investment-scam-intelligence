import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_target_text_corpus_v1_multilingual_supply_v1 import audit
from scripts.verify_target_text_corpus_v1_multilingual_supply_audit_v1 import verify


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "target_text_corpus_v1_multilingual_supply_audit_v1.json"


class VerifyTargetTextCorpusV1MultilingualSupplyAuditV1Tests(unittest.TestCase):
    def test_current_frozen_inputs_pass_with_all_language_unknown(self) -> None:
        report = audit(CONFIG)
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.json"
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            result = verify(CONFIG, report_path)
        self.assertEqual(result["status"], "PASS_ALL_ROWS_UNKNOWN_LANGUAGE_GATE_CLOSED")
        self.assertEqual(result["checks"]["channel_count"], 4)
        self.assertEqual(result["checks"]["audited_rows"], 16504)
        self.assertEqual(result["checks"]["unknown_language_rows"], 16504)
        self.assertEqual(result["errors"], [])


if __name__ == "__main__":
    unittest.main()
