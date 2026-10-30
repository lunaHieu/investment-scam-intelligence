import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.execute_target_text_corpus_v1_parser_bound_content_diagnostic_v1 import (
    run_with_injected_transport,
)
from scripts.execute_target_text_corpus_v1_parser_bound_content_v1 import TransportResponse
from scripts.process_target_text_corpus_v1_parser_bound_pdf_lifecycle_v2 import PdfLifecycleProcessError
from scripts.verify_target_text_corpus_v1_parser_bound_content_release_v1 import ROOT


def source_rows():
    release = json.loads((ROOT / "configs/target_text_corpus_v1_parser_bound_content_release_v1.json").read_text(encoding="utf-8"))
    return {row["resource_id"]: row for row in release["resources"]}


class DiagnosticExecutorV1Tests(unittest.TestCase):
    def test_parser_failure_continues_exact_two_rows_with_pacing_and_no_raw_retention(self):
        resources = source_rows()
        calls = []
        pauses = []

        def transport(resource):
            rid = resource["resource_id"]
            calls.append(rid)
            body = b"%PDF-1.7 synthetic" if rid == "PBC05" else b'{"message":"secret payload"}'
            return TransportResponse(
                status_code=200,
                final_url=resource["url"],
                headers={"Content-Type": resource["content_types"][0]},
                body=body,
            )

        def fail_pdf(*_args):
            completed = subprocess.CompletedProcess(
                args=["extractor"],
                returncode=2,
                stdout=json.dumps({"status": "PDF_EXTRACTION_REJECTED", "diagnostic_code": "PDF_OPEN_OR_PARSE_ERROR"}),
                stderr="secret exception message",
            )
            raise PdfLifecycleProcessError("SECTION_EXTRACTION", completed)

        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as directory:
            output = Path(directory) / "result.json"
            partial = Path(str(output) + ".partial")
            result = run_with_injected_transport(
                transport, output, partial, pdf_processor=fail_pdf, sleep_fn=pauses.append
            )
            self.assertEqual(calls, ["PBC05", "PBC08"])
            self.assertEqual(pauses, [30.0])
            self.assertEqual([row["outcome"] for row in result["result"]["resources"]], ["PARSER_REJECTED", "PARSER_REJECTED"])
            self.assertEqual(result["result"]["resources"][0]["diagnostic_code"], "PDF_LIFECYCLE_PDF_OPEN_OR_PARSE_ERROR")
            self.assertEqual(result["result"]["resources"][1]["diagnostic_code"], "PARSER_REJECTED_FORBIDDEN_DATASET_KEY_PRESENT")
            self.assertTrue(all(row["raw_response_retained"] is False for row in result["result"]["resources"]))
            serialized = output.read_text(encoding="utf-8")
            self.assertNotIn("secret payload", serialized)
            self.assertNotIn("secret exception message", serialized)
            self.assertFalse(partial.exists())
            self.assertEqual(result["verification"]["status"], "PASS_PARSER_BOUND_DIAGNOSTIC_RESULT_VERIFIED")

    def test_existing_output_blocks_before_transport(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as directory:
            output = Path(directory) / "result.json"
            output.write_text("preserve", encoding="utf-8")
            calls = []
            with self.assertRaises(FileExistsError):
                run_with_injected_transport(lambda resource: calls.append(resource), output, Path(str(output) + ".partial"))
            self.assertEqual(calls, [])
            self.assertEqual(output.read_text(encoding="utf-8"), "preserve")


if __name__ == "__main__":
    unittest.main()
