import json
import subprocess
import unittest

from scripts.execute_target_text_corpus_v1_parser_bound_content_v1 import (
    TransportResponse,
    process_transport_response,
)
from scripts.process_target_text_corpus_v1_parser_bound_pdf_lifecycle_v2 import (
    PdfLifecycleProcessError,
)
from scripts.verify_target_text_corpus_v1_parser_bound_content_release_v1 import RELEASE


def pbc08_resource():
    return json.loads(RELEASE.read_text(encoding="utf-8"))["resources"][7]


def pbc08_response(body):
    resource = pbc08_resource()
    return TransportResponse(
        status_code=200,
        final_url=resource["url"],
        headers={"Content-Type": "application/json; charset=utf-8"},
        body=json.dumps(body).encode("utf-8"),
    )


class PbcStructuredDiagnosticsV1Tests(unittest.TestCase):
    def test_pbc08_forbidden_key_code_does_not_disclose_key(self):
        row = process_transport_response(pbc08_resource(), pbc08_response({"message": "private"}))
        self.assertEqual(row["diagnostic_code"], "PARSER_REJECTED_FORBIDDEN_DATASET_KEY_PRESENT")
        self.assertNotIn("message", row["diagnostic_code"])
        self.assertFalse(row["raw_response_retained"])

    def test_pbc08_invalid_commit_list_code(self):
        row = process_transport_response(pbc08_resource(), pbc08_response({"items": []}))
        self.assertEqual(row["diagnostic_code"], "PARSER_REJECTED_COMMIT_LIST_MISSING_OR_INVALID")

    def test_pbc08_non_object_entry_code(self):
        row = process_transport_response(pbc08_resource(), pbc08_response(["not-an-object"]))
        self.assertEqual(row["diagnostic_code"], "PARSER_REJECTED_COMMIT_ENTRY_NOT_OBJECT")

    def test_pbc08_invalid_commit_id_code(self):
        row = process_transport_response(pbc08_resource(), pbc08_response([{"id": "short"}]))
        self.assertEqual(row["diagnostic_code"], "PARSER_REJECTED_COMMIT_ID_INVALID")

    def test_pdf_lifecycle_accepts_only_bounded_extractor_code(self):
        completed = subprocess.CompletedProcess(
            args=["extractor"],
            returncode=2,
            stdout=json.dumps({
                "status": "PDF_EXTRACTION_REJECTED",
                "diagnostic_code": "PDF_OPEN_OR_PARSE_ERROR",
            }),
            stderr="sensitive exception text",
        )
        error = PdfLifecycleProcessError("SECTION_EXTRACTION", completed)
        self.assertEqual(error.diagnostic_code, "PDF_OPEN_OR_PARSE_ERROR")
        self.assertNotIn("sensitive", str(error))
        self.assertNotIn("sensitive", json.dumps(error.details))

    def test_pdf_lifecycle_rejects_unstructured_or_injected_code(self):
        completed = subprocess.CompletedProcess(
            args=["extractor"],
            returncode=2,
            stdout=json.dumps({"status": "PDF_EXTRACTION_REJECTED", "diagnostic_code": "raw secret"}),
            stderr="secret",
        )
        error = PdfLifecycleProcessError("SECTION_EXTRACTION", completed)
        self.assertIsNone(error.diagnostic_code)
        self.assertNotIn("secret", str(error))


if __name__ == "__main__":
    unittest.main()
