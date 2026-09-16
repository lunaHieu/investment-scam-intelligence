import sys
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from audit_text_baseline_v2_external_readiness import (
    assess_reporting_gate,
    profile_crimson_raw,
    profile_crimson_review,
    profile_ubcknn,
    read_xlsx_rows,
    table_records,
)


class TextBaselineV2ExternalReadinessTests(unittest.TestCase):
    def test_crimson_raw_text_profile_does_not_treat_url_or_ioc_as_text(self):
        result = profile_crimson_raw(
            [{"url": "example.test", "ioc": {"email": "a@example.test"}}]
        )
        self.assertEqual(result["rows_with_observed_text"], 0)
        self.assertEqual(result["recognized_observed_text_fields"], [])

    def test_crimson_review_profile_counts_completed_fields(self):
        records = [
            {
                "queue_id": "Q1",
                "artifact_id": "A1",
                "domain": "example.test",
                "url_canonical": "https://example.test",
                "review_status": "RECONCILED",
                "ground_truth_status": "CONFIRMED",
                "evidence_url_1": "https://regulator.test/warning",
                "evidence_url_2": None,
                "review_rationale": "matched",
                "review_gate": "PASS",
            }
        ]
        result = profile_crimson_review(records)
        self.assertEqual(result["reconciled_rows"], 1)
        self.assertEqual(result["ground_truth_status_populated"], 1)
        self.assertEqual(result["evidence_url_populated"], 1)
        self.assertEqual(result["observed_text_rows"], 0)

    def test_ubcknn_warning_documents_are_not_external_text_examples(self):
        result = profile_ubcknn(
            {
                "warning_artifacts": [
                    {
                        "artifact_type": "WARNING_DOCUMENT",
                        "has_text": False,
                        "text": None,
                    }
                ],
                "cases": [{"ground_truth_status": "UNCERTAIN"}],
            }
        )
        self.assertEqual(result["eligible_external_text_records"], 0)
        self.assertEqual(result["warning_artifacts_with_observed_text"], 0)

    def test_reporting_gate_requires_both_classes(self):
        policy = {
            "pilot_reporting_gate": {
                "minimum_total_eligible_records": 20,
                "minimum_confirmed_records": 10,
                "minimum_legitimate_records": 10,
            }
        }
        self.assertFalse(assess_reporting_gate(policy, 20, 0)["reporting_allowed"])
        self.assertTrue(assess_reporting_gate(policy, 10, 10)["reporting_allowed"])

    def test_minimal_xlsx_reader_resolves_shared_strings(self):
        with TemporaryDirectory(dir=ROOT) as temp_dir:
            path = Path(temp_dir) / "sample.xlsx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(
                    "xl/workbook.xml",
                    '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                    '<sheets><sheet name="Review queue" sheetId="1" r:id="rId1"/></sheets></workbook>',
                )
                archive.writestr(
                    "xl/_rels/workbook.xml.rels",
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>',
                )
                archive.writestr(
                    "xl/sharedStrings.xml",
                    '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                    '<si><t>review_status</t></si><si><t>UNREVIEWED</t></si></sst>',
                )
                archive.writestr(
                    "xl/worksheets/sheet1.xml",
                    '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                    '<sheetData><row r="1"><c r="A1" t="s"><v>0</v></c></row>'
                    '<row r="2"><c r="A2" t="s"><v>1</v></c></row></sheetData></worksheet>',
                )
            rows = read_xlsx_rows(path, "Review queue")
            self.assertEqual(table_records(rows), [{"review_status": "UNREVIEWED"}])


if __name__ == "__main__":
    unittest.main()
