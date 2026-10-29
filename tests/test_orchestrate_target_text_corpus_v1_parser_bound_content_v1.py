import json
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.dry_run_target_text_corpus_v1_parser_bound_content_v1 import (
    synthetic_transport,
)
from scripts.execute_target_text_corpus_v1_parser_bound_content_v1 import (
    TransportResponse,
)
from scripts.orchestrate_target_text_corpus_v1_parser_bound_content_v1 import (
    execute_live,
    execute_with_injected_transport_for_test,
)
from scripts.verify_target_text_corpus_v1_parser_bound_content_release_v1 import (
    RELEASE,
)


def resources():
    return json.loads(RELEASE.read_text(encoding="utf-8"))["resources"]


class ParserBoundProductionOrchestratorV1Tests(unittest.TestCase):
    def paths(self, directory: str):
        root = Path(directory)
        return root / "result.json", root / "result.json.partial"

    def test_all_success_is_verified_then_atomically_finalized(self):
        with tempfile.TemporaryDirectory() as directory:
            output, partial = self.paths(directory)
            value = execute_with_injected_transport_for_test(
                synthetic_transport, output, partial
            )
            self.assertTrue(output.is_file())
            self.assertFalse(partial.exists())
            self.assertFalse(Path(str(partial) + ".tmp").exists())
            self.assertEqual(value["verification"]["success"], 8)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["summary"]["success"], 8)

    def test_failure_stops_requests_but_finalizes_honest_report(self):
        calls = []
        def transport(resource):
            calls.append(resource["resource_id"])
            if resource["resource_id"] == "PBC02":
                return TransportResponse(200, resource["url"], {"Content-Type":"text/html"}, b"bad")
            return synthetic_transport(resource)
        with tempfile.TemporaryDirectory() as directory:
            output, partial = self.paths(directory)
            value = execute_with_injected_transport_for_test(transport, output, partial)
            self.assertEqual(calls, ["PBC01", "PBC02"])
            summary = value["result"]["summary"]
            self.assertEqual(summary["success"], 1)
            self.assertEqual(summary["parser_rejected"], 1)
            self.assertEqual(summary["skipped_after_failure"], 6)
            self.assertTrue(output.exists())
            self.assertFalse(partial.exists())

    def test_pdf_lifecycle_output_is_used_and_gate_stays_pending(self):
        calls = []
        def pdf_processor(resource, data):
            calls.append(resource["resource_id"])
            return {
                "status":"PDF_EXTRACTED_VISUAL_REVIEW_PENDING",
                "sha256":hashlib.sha256(data).hexdigest(),
                "bytes":len(data),
                "page_count":1,
                "sections":[],
                "rendered_page_count":1,
                "render_integrity_status":"PASS_PNG_STRUCTURE_AND_PAGE_COUNT",
                "visual_review_status":"PENDING_REQUIRED",
                "temporary_artifacts_deleted":True,
            }
        with tempfile.TemporaryDirectory() as directory:
            output, partial = self.paths(directory)
            value = execute_with_injected_transport_for_test(
                synthetic_transport,
                output,
                partial,
                pdf_processor=pdf_processor,
            )
            self.assertEqual(calls, ["PBC05"])
            pdf = value["result"]["resources"][4]["structured_output"]
            self.assertEqual(pdf["visual_review_status"], "PENDING_REQUIRED")
            self.assertTrue(pdf["temporary_artifacts_deleted"])
            self.assertFalse(value["result"]["decision"]["evidence_acceptance_allowed"])

    def test_pdf_lifecycle_failure_stops_after_pbc05(self):
        transport_calls = []
        def transport(resource):
            transport_calls.append(resource["resource_id"])
            return synthetic_transport(resource)
        def reject_pdf(resource, data):
            raise ValueError("synthetic PDF lifecycle rejection")
        with tempfile.TemporaryDirectory() as directory:
            output, partial = self.paths(directory)
            value = execute_with_injected_transport_for_test(
                transport,
                output,
                partial,
                pdf_processor=reject_pdf,
            )
            self.assertEqual(transport_calls, [f"PBC{number:02}" for number in range(1, 6)])
            summary = value["result"]["summary"]
            self.assertEqual(summary["success"], 4)
            self.assertEqual(summary["parser_rejected"], 1)
            self.assertEqual(summary["skipped_after_failure"], 3)
            self.assertEqual(
                value["result"]["resources"][4]["diagnostic_code"],
                "PDF_LIFECYCLE_VALUEERROR",
            )

    def test_existing_partial_or_final_prevents_any_transport_call(self):
        for existing_name in ("result.json", "result.json.partial", "result.json.partial.tmp"):
            with self.subTest(existing_name=existing_name), tempfile.TemporaryDirectory() as directory:
                output, partial = self.paths(directory)
                existing = Path(directory) / existing_name
                existing.write_text("preserve", encoding="utf-8")
                calls = []
                with self.assertRaises(FileExistsError):
                    execute_with_injected_transport_for_test(
                        lambda resource:calls.append(resource) or synthetic_transport(resource),
                        output,
                        partial,
                    )
                self.assertEqual(calls, [])
                self.assertEqual(existing.read_text(encoding="utf-8"), "preserve")

    def test_verifier_failure_preserves_partial_and_never_creates_final(self):
        def reject(_):
            raise ValueError("synthetic independent rejection")
        with tempfile.TemporaryDirectory() as directory:
            output, partial = self.paths(directory)
            with self.assertRaisesRegex(ValueError, "synthetic independent rejection"):
                execute_with_injected_transport_for_test(
                    synthetic_transport, output, partial, verifier=reject
                )
            self.assertFalse(output.exists())
            self.assertTrue(partial.exists())
            self.assertEqual(
                json.loads(partial.read_text(encoding="utf-8"))["result_id"],
                "ISI_TARGET_TEXT_CORPUS_V1_PARSER_BOUND_CONTENT_RESULT_V1",
            )

    def test_live_execution_is_blocked_before_real_opener(self):
        with patch("scripts.http_transport_target_text_corpus_v1_parser_bound_content_v1.urllib.request.build_opener") as builder:
            with self.assertRaises(PermissionError):
                execute_live()
            builder.assert_not_called()


if __name__ == "__main__":
    unittest.main()
