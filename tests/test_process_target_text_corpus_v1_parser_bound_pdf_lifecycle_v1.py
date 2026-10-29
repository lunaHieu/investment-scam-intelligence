import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.process_target_text_corpus_v1_parser_bound_pdf_lifecycle_v1 import (
    process_pdf_lifecycle,
    resolve_runtime_paths,
)
from scripts.verify_target_text_corpus_v1_parser_bound_content_release_v1 import (
    RELEASE,
)

import json


def pdf_resource():
    return json.loads(RELEASE.read_text(encoding="utf-8"))["resources"][4]


def create_fixture(path: Path) -> None:
    python, _, _ = resolve_runtime_paths()
    source = (
        "from reportlab.lib.pagesizes import letter;"
        "from reportlab.pdfgen import canvas;"
        "import sys;"
        "c=canvas.Canvas(sys.argv[1],pagesize=letter);"
        "c.setFont('Helvetica-Bold',16);"
        "c.drawString(72,720,'Synthetic Parser-Bound PDF Fixture');"
        "c.setFont('Helvetica',11);"
        "c.drawString(72,690,'Data sources: synthetic metadata only.');"
        "c.drawString(72,670,'Annotation: no dataset records are present.');"
        "c.showPage();"
        "c.setFont('Helvetica-Bold',14);"
        "c.drawString(72,720,'Ethics and Privacy');"
        "c.setFont('Helvetica',11);"
        "c.drawString(72,690,'Privacy: this fixture contains no personal data.');"
        "c.save()"
    )
    subprocess.run([str(python), "-c", source, str(path)], check=True)


class ParserBoundPdfLifecycleV1Tests(unittest.TestCase):
    def test_extracts_renders_keeps_gate_pending_and_deletes_temporary_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixture.pdf"
            lifecycle_root = root / "lifecycle"
            create_fixture(fixture)
            result = process_pdf_lifecycle(
                pdf_resource(), fixture.read_bytes(), temporary_root=lifecycle_root
            )
            self.assertEqual(result["status"], "PDF_EXTRACTED_VISUAL_REVIEW_PENDING")
            self.assertEqual(result["page_count"], 2)
            self.assertEqual(result["rendered_page_count"], 2)
            self.assertEqual(result["visual_review_status"], "PENDING_REQUIRED")
            self.assertTrue(result["temporary_artifacts_deleted"])
            self.assertEqual(len(result["sections"]), 2)
            self.assertEqual(list(lifecycle_root.iterdir()), [])

    def test_invalid_pdf_is_rejected_without_creating_temporary_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "magic"):
                process_pdf_lifecycle(
                    pdf_resource(), b"not-a-pdf", temporary_root=root
                )
            self.assertEqual(list(root.iterdir()), [])

    def test_renderer_failure_still_deletes_pdf_and_render_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixture.pdf"
            lifecycle_root = root / "lifecycle"
            create_fixture(fixture)
            python, _, pdfinfo = resolve_runtime_paths()
            broken_renderer = root / "broken-pdftoppm.exe"
            broken_renderer.write_bytes(b"not an executable")
            with self.assertRaises(OSError):
                process_pdf_lifecycle(
                    pdf_resource(),
                    fixture.read_bytes(),
                    temporary_root=lifecycle_root,
                    python_path=python,
                    pdftoppm_path=broken_renderer,
                    pdfinfo_path=pdfinfo,
                )
            self.assertEqual(list(lifecycle_root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
