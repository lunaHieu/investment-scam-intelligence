import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.dry_run_target_text_corpus_v1_parser_bound_content_v1 import synthetic_transport
from scripts.execute_target_text_corpus_v1_parser_bound_content_supplemental_v1 import (
    execute_with_injected_transport_for_test,
)
from scripts.process_target_text_corpus_v1_parser_bound_pdf_lifecycle_v2 import PdfLifecycleProcessError


class ParserBoundSupplementalExecutorV1Tests(unittest.TestCase):
    def paths(self, directory):
        root = Path(directory)
        return root / "result.json", root / "result.json.partial"

    def test_pbc05_parser_failure_continues_three_never_attempted_rows(self):
        calls = []
        def transport(resource):
            calls.append(resource["resource_id"])
            return synthetic_transport(resource)
        def reject_pdf(resource, body):
            raise PdfLifecycleProcessError(
                "SECTION_EXTRACTION",
                subprocess.CompletedProcess([], 7, stdout="", stderr="bounded failure"),
            )
        with tempfile.TemporaryDirectory() as directory:
            output, partial = self.paths(directory)
            value = execute_with_injected_transport_for_test(transport, reject_pdf, output, partial)
            self.assertEqual(calls, ["PBC05", "PBC06", "PBC07", "PBC08"])
            self.assertEqual(value["result"]["resources"][0]["outcome"], "PARSER_REJECTED")
            self.assertEqual(value["result"]["summary"]["success"], 3)
            self.assertEqual(value["verification"]["status"], "PASS_PARSER_BOUND_SUPPLEMENTAL_RESULT_VERIFIED")
            self.assertTrue(output.exists())
            self.assertFalse(partial.exists())

    def test_transport_failure_stops_provider_requests(self):
        calls = []
        def transport(resource):
            calls.append(resource["resource_id"])
            if resource["resource_id"] == "PBC06":
                raise OSError("synthetic transport failure")
            return synthetic_transport(resource)
        def accept_pdf(resource, body):
            return {"status":"PDF_EXTRACTED_VISUAL_REVIEW_PENDING","sha256":__import__("hashlib").sha256(body).hexdigest(),"bytes":len(body),"page_count":1,"sections":[],"rendered_page_count":1,"render_integrity_status":"PASS_PNG_STRUCTURE_AND_PAGE_COUNT","visual_review_status":"PENDING_REQUIRED","temporary_artifacts_deleted":True}
        with tempfile.TemporaryDirectory() as directory:
            output, partial = self.paths(directory)
            value = execute_with_injected_transport_for_test(transport, accept_pdf, output, partial)
            self.assertEqual(calls, ["PBC05", "PBC06"])
            self.assertEqual(value["result"]["summary"]["transport_error"], 1)
            self.assertEqual(value["result"]["summary"]["skipped_after_failure"], 2)

    def test_existing_output_blocks_before_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            output, partial = self.paths(directory)
            output.write_text("preserve", encoding="utf-8")
            calls = []
            with self.assertRaises(FileExistsError):
                execute_with_injected_transport_for_test(lambda resource: calls.append(resource), lambda *_: {}, output, partial)
            self.assertEqual(calls, [])
            self.assertEqual(output.read_text(encoding="utf-8"), "preserve")


if __name__ == "__main__":
    unittest.main()
