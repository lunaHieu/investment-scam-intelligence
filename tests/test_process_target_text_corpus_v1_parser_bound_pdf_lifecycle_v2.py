import json
import tempfile
import unittest
from pathlib import Path

from scripts.process_target_text_corpus_v1_parser_bound_pdf_lifecycle_v2 import (
    PdfLifecycleProcessError,
    process_pdf_lifecycle_v2,
    resolve_runtime_paths,
)
from scripts.verify_target_text_corpus_v1_parser_bound_content_release_v1 import RELEASE
from tests.test_process_target_text_corpus_v1_parser_bound_pdf_lifecycle_v1 import create_fixture


def pdf_resource():
    return json.loads(RELEASE.read_text(encoding="utf-8"))["resources"][4]


class ParserBoundPdfLifecycleV2Tests(unittest.TestCase):
    def test_success_preserves_v1_output_contract_and_deletes_temporaries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixture.pdf"
            lifecycle_root = root / "lifecycle"
            create_fixture(fixture)
            result = process_pdf_lifecycle_v2(
                pdf_resource(), fixture.read_bytes(), temporary_root=lifecycle_root
            )
            self.assertEqual(result["page_count"], 2)
            self.assertEqual(result["rendered_page_count"], 2)
            self.assertEqual(result["visual_review_status"], "PENDING_REQUIRED")
            self.assertTrue(result["temporary_artifacts_deleted"])
            self.assertEqual(list(lifecycle_root.iterdir()), [])

    def test_nonzero_pdfinfo_records_hash_only_stage_diagnostic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixture.pdf"
            lifecycle_root = root / "lifecycle"
            create_fixture(fixture)
            python, pdftoppm, _ = resolve_runtime_paths()
            with self.assertRaises(PdfLifecycleProcessError) as raised:
                process_pdf_lifecycle_v2(
                    pdf_resource(),
                    fixture.read_bytes(),
                    temporary_root=lifecycle_root,
                    python_path=python,
                    pdftoppm_path=pdftoppm,
                    pdfinfo_path=python,
                )
            details = raised.exception.details
            self.assertEqual(details["stage"], "PDFINFO")
            self.assertNotEqual(details["returncode"], 0)
            self.assertEqual(
                set(details),
                {"stage", "returncode", "stdout_bytes", "stdout_sha256", "stderr_bytes", "stderr_sha256"},
            )
            self.assertEqual(list(lifecycle_root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
