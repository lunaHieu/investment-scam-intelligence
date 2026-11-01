import json
import subprocess
import unittest

from scripts.pbc_safe_diagnostic_contract_v1 import (
    classify_forbidden_key_categories,
    diagnose_pdf_child_failure,
)


FORBIDDEN = ["rows", "row", "content", "text", "message", "examples", "preview"]


class PbcSafeDiagnosticContractV1Tests(unittest.TestCase):
    def test_forbidden_key_diagnostic_returns_only_categories(self):
        value = {
            "commits": [
                {"id": "synthetic-id", "metadata": {"MeSsAgE": "secret fixture value"}},
                {"nested": {"ROWS": ["synthetic record"]}},
            ]
        }
        result = classify_forbidden_key_categories(value, FORBIDDEN)
        self.assertEqual(result["diagnostic_code"], "FORBIDDEN_DATASET_KEY_PRESENT")
        self.assertEqual(result["key_categories"], ["FREEFORM_MESSAGE", "RECORD_COLLECTION"])
        serialized = json.dumps(result)
        for forbidden_text in ("MeSsAgE", "ROWS", "secret fixture value", "synthetic record", "metadata"):
            self.assertNotIn(forbidden_text, serialized)

    def test_safe_metadata_without_forbidden_keys_has_no_diagnostic(self):
        value = {"commits": [{"id": "synthetic-id", "title": "metadata"}]}
        self.assertEqual(
            classify_forbidden_key_categories(value, FORBIDDEN),
            {"diagnostic_code": None, "key_categories": []},
        )

    def test_unknown_configured_key_maps_to_generic_category(self):
        result = classify_forbidden_key_categories({"opaque": "value"}, ["opaque"])
        self.assertEqual(result, {
            "diagnostic_code": "FORBIDDEN_DATASET_KEY_PRESENT",
            "key_categories": ["UNKNOWN_CONFIGURED_KEY"],
        })
        self.assertNotIn("opaque", json.dumps(result))

    def test_child_exception_class_is_allowlisted_and_message_is_discarded(self):
        message = "Traceback (most recent call last):\nModuleNotFoundError: No module named 'private-module'"
        completed = subprocess.CompletedProcess(
            args=["synthetic-python"], returncode=1, stdout="", stderr=message
        )
        result = diagnose_pdf_child_failure("SECTION_EXTRACTION", completed)
        self.assertEqual(result["child_exception_class"], "ModuleNotFoundError")
        self.assertEqual(result["diagnostic_code"], "PDF_CHILD_NONZERO_NO_STRUCTURED_DIAGNOSTIC")
        self.assertEqual(result["stage"], "SECTION_EXTRACTION")
        self.assertNotIn("private-module", json.dumps(result))
        self.assertNotIn("Traceback", json.dumps(result))
        self.assertNotIn("stderr_text", result)

    def test_unknown_exception_class_is_collapsed(self):
        completed = subprocess.CompletedProcess(
            args=["synthetic-python"], returncode=1, stdout=b"", stderr=b"SecretError: private detail"
        )
        result = diagnose_pdf_child_failure("SECTION_EXTRACTION", completed)
        self.assertEqual(result["child_exception_class"], "OTHER_EXCEPTION")
        self.assertNotIn("SecretError", json.dumps(result))
        self.assertNotIn("private detail", json.dumps(result))

    def test_only_allowlisted_extractor_codes_are_retained(self):
        completed = subprocess.CompletedProcess(
            args=["synthetic-python"],
            returncode=2,
            stdout=json.dumps({"status": "PDF_EXTRACTION_REJECTED", "diagnostic_code": "PDF_INVALID_MAGIC"}),
            stderr="",
        )
        result = diagnose_pdf_child_failure("PDFINFO", completed)
        self.assertEqual(result["diagnostic_code"], "PDF_INVALID_MAGIC")
        self.assertIsNone(result["child_exception_class"])

    def test_untrusted_extractor_code_and_stage_are_normalized(self):
        completed = subprocess.CompletedProcess(
            args=["synthetic-python"],
            returncode=2,
            stdout=json.dumps({"status": "PDF_EXTRACTION_REJECTED", "diagnostic_code": "secret-value"}),
            stderr="",
        )
        result = diagnose_pdf_child_failure("UNTRUSTED_STAGE", completed)
        self.assertEqual(result["diagnostic_code"], "PDF_CHILD_NONZERO_NO_STRUCTURED_DIAGNOSTIC")
        self.assertEqual(result["stage"], "UNKNOWN_STAGE")
        self.assertNotIn("secret-value", json.dumps(result))

    def test_oversized_stdout_is_hashed_but_not_parsed(self):
        stdout = b" " * (64 * 1024 + 1)
        completed = subprocess.CompletedProcess(
            args=["synthetic-python"], returncode=2, stdout=stdout, stderr=b""
        )
        result = diagnose_pdf_child_failure("SECTION_EXTRACTION", completed)
        self.assertEqual(result["stdout_bytes"], len(stdout))
        self.assertEqual(result["diagnostic_code"], "PDF_CHILD_NONZERO_NO_STRUCTURED_DIAGNOSTIC")


if __name__ == "__main__":
    unittest.main()
