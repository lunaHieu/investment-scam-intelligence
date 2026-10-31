"""Synthetic, offline boundary checks for the PBC parser follow-up."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.execute_target_text_corpus_v1_parser_bound_content_v1 import (
    ParserRejection,
    parse_hf_commits,
)
from scripts.process_target_text_corpus_v1_parser_bound_pdf_lifecycle_v2 import (
    PdfLifecycleProcessError,
)
from scripts.verify_target_text_corpus_v1_parser_bound_content_release_v1 import (
    RELEASE,
    ROOT,
)


def pbc08_contract() -> dict:
    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    return next(row for row in release["resources"] if row["resource_id"] == "PBC08")


class PbcOfflineBoundaryReviewV1Tests(unittest.TestCase):
    def test_synthetic_commit_metadata_is_accepted_and_unselected_fields_are_dropped(self):
        resource = pbc08_contract()
        commit_id = "a" * 40
        parsed = parse_hf_commits(
            {
                "commits": [
                    {
                        "id": commit_id,
                        "title": "synthetic fixture",
                        "createdAt": "2026-01-01T00:00:00Z",
                        "authors": [{"username": "fixture-user"}],
                        "unselected_metadata": "not retained",
                    }
                ]
            },
            resource["forbidden_keys"],
        )
        self.assertEqual(parsed["commits"][0]["id"], commit_id)
        self.assertEqual(parsed["commits"][0]["title"], "synthetic fixture")
        self.assertEqual(parsed["commits"][0]["authors"], ["fixture-user"])
        self.assertNotIn("unselected_metadata", json.dumps(parsed))

    def test_each_configured_forbidden_key_is_rejected_at_nested_depth(self):
        resource = pbc08_contract()
        for key in resource["forbidden_keys"]:
            with self.subTest(forbidden_key=key):
                value = {"commits": [{"id": "a" * 40, "nested": {key: "synthetic"}}]}
                with self.assertRaises(ParserRejection) as caught:
                    parse_hf_commits(value, resource["forbidden_keys"])
                self.assertEqual(caught.exception.code, "FORBIDDEN_DATASET_KEY_PRESENT")
                self.assertNotIn(key, str(caught.exception))

    def test_forbidden_key_matching_is_case_insensitive_and_value_free(self):
        resource = pbc08_contract()
        with self.assertRaises(ParserRejection) as caught:
            parse_hf_commits(
                {"commits": [{"id": "a" * 40, "nested": {"MeSsAgE": "synthetic"}}]},
                resource["forbidden_keys"],
            )
        self.assertEqual(caught.exception.code, "FORBIDDEN_DATASET_KEY_PRESENT")
        self.assertNotIn("synthetic", str(caught.exception))
        self.assertNotIn("MeSsAgE", str(caught.exception))

    def test_pbc05_unstructured_child_failure_retains_only_stage_and_hashes(self):
        stderr = "synthetic child startup traceback; no source document involved"
        completed = subprocess.CompletedProcess(
            args=["synthetic-python", "-m", "synthetic.extractor"],
            returncode=1,
            stdout="",
            stderr=stderr,
        )
        error = PdfLifecycleProcessError("SECTION_EXTRACTION", completed)
        self.assertIsNone(error.diagnostic_code)
        self.assertEqual(error.details["stdout_bytes"], 0)
        self.assertEqual(error.details["stderr_bytes"], len(stderr.encode("utf-8")))
        self.assertEqual(
            set(error.details),
            {"stage", "returncode", "stdout_bytes", "stdout_sha256", "stderr_bytes", "stderr_sha256"},
        )
        self.assertNotIn(stderr, str(error))
        self.assertNotIn(stderr, json.dumps(error.details))

    def test_extractor_emits_a_safe_code_for_a_synthetic_invalid_pdf(self):
        with tempfile.TemporaryDirectory(prefix="pbc-offline-boundary-") as directory:
            temporary_root = Path(directory)
            sample = temporary_root / "synthetic-invalid.pdf"
            sample.write_bytes(b"synthetic bytes, not a PDF")
            # The extractor imports pdfplumber before validating the file. A
            # tiny inert stub keeps this test independent of optional runtimes.
            (temporary_root / "pdfplumber.py").write_text("__version__ = 'synthetic'\n", encoding="utf-8")
            environment = os.environ.copy()
            old_pythonpath = environment.get("PYTHONPATH")
            environment["PYTHONPATH"] = str(temporary_root) + (os.pathsep + old_pythonpath if old_pythonpath else "")
            completed = subprocess.run(
                [sys.executable, "-m", "scripts.extract_scambench_pdf_sections_v1", str(sample)],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=environment,
            )
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(payload["status"], "PDF_EXTRACTION_REJECTED")
        self.assertEqual(payload["diagnostic_code"], "PDF_INVALID_MAGIC")
        self.assertEqual(completed.stderr, "")


if __name__ == "__main__":
    unittest.main()
