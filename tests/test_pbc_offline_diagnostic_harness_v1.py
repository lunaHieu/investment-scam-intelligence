import json
import subprocess
import unittest
from unittest.mock import patch

from scripts.execute_target_text_corpus_v1_parser_bound_content_v1 import ParserRejection
from scripts.pbc_offline_diagnostic_harness_v1 import (
    diagnose_pbc05_child_fixture,
    diagnose_pbc08_fixture,
)


FORBIDDEN = ["rows", "row", "content", "text", "message", "examples", "preview"]


class PbcOfflineDiagnosticHarnessV1Tests(unittest.TestCase):
    def test_valid_synthetic_commit_is_checked_without_returning_its_values(self):
        value = {
            "commits": [
                {
                    "id": "a" * 40,
                    "title": "synthetic title",
                    "createdAt": "2026-01-01T00:00:00Z",
                    "authors": [{"username": "fixture-user"}],
                }
            ]
        }
        result = diagnose_pbc08_fixture(value, FORBIDDEN)
        self.assertEqual(result, {
            "status": "PARSER_ACCEPTED",
            "diagnostic_code": None,
            "key_categories": [],
        })
        serialized = json.dumps(result)
        for value_part in ("synthetic title", "fixture-user", "a" * 40):
            self.assertNotIn(value_part, serialized)

    def test_forbidden_synthetic_field_is_classified_without_name_or_value(self):
        result = diagnose_pbc08_fixture(
            {"commits": [{"id": "a" * 40, "nested": {"message": "synthetic secret"}}]},
            FORBIDDEN,
        )
        self.assertEqual(result, {
            "status": "PARSER_REJECTED",
            "diagnostic_code": "FORBIDDEN_DATASET_KEY_PRESENT",
            "key_categories": ["FREEFORM_MESSAGE"],
        })
        self.assertNotIn("message", json.dumps(result))
        self.assertNotIn("synthetic secret", json.dumps(result))

    def test_commit_schema_errors_use_allowlisted_codes(self):
        missing_list = diagnose_pbc08_fixture({"items": []}, FORBIDDEN)
        invalid_id = diagnose_pbc08_fixture({"commits": [{"id": "private-short-id"}]}, FORBIDDEN)
        self.assertEqual(missing_list["diagnostic_code"], "COMMIT_LIST_MISSING_OR_INVALID")
        self.assertEqual(invalid_id["diagnostic_code"], "COMMIT_ID_INVALID")
        self.assertNotIn("private-short-id", json.dumps(invalid_id))

    def test_pdf_child_integration_keeps_only_safe_class_stage_and_hashes(self):
        message = "ModuleNotFoundError: No module named 'synthetic-secret'"
        completed = subprocess.CompletedProcess(
            args=["synthetic-python"], returncode=1, stdout="", stderr=message
        )
        result = diagnose_pbc05_child_fixture("SECTION_EXTRACTION", completed)
        self.assertEqual(result["stage"], "SECTION_EXTRACTION")
        self.assertEqual(result["child_exception_class"], "ModuleNotFoundError")
        self.assertNotIn("synthetic-secret", json.dumps(result))
        self.assertNotIn("stderr_text", result)

    def test_parser_rejection_uses_allowlisted_code(self):
        result = diagnose_pbc08_fixture({"commits": [None]}, FORBIDDEN)
        self.assertEqual(result["diagnostic_code"], "COMMIT_ENTRY_NOT_OBJECT")
        self.assertNotIn("None", json.dumps(result))

    def test_unrecognized_parser_code_is_collapsed(self):
        with patch(
            "scripts.pbc_offline_diagnostic_harness_v1.parse_hf_commits",
            side_effect=ParserRejection("secret-parser-code"),
        ):
            result = diagnose_pbc08_fixture({"commits": []}, FORBIDDEN)
        self.assertEqual(result["diagnostic_code"], "COMMIT_METADATA_REJECTED")
        self.assertNotIn("secret-parser-code", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
