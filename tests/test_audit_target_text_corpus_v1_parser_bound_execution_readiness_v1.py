import unittest

from scripts.audit_target_text_corpus_v1_parser_bound_execution_readiness_v1 import (
    HTTP_TRANSPORT,
    audit,
)


class ParserBoundExecutionReadinessAuditV1Tests(unittest.TestCase):
    def test_local_stack_is_ready_only_for_commit_review(self):
        result = audit()
        self.assertEqual(
            result["status"],
            "PASS_STACK_INTEGRITY_VERIFIED_EXECUTION_REMAINS_CLOSED",
        )
        self.assertIn(result["repository_state"], {"PRE_COMMIT_LOCAL", "COMMITTED_TRACKED"})
        self.assertEqual(result["managed_files"], 23)
        self.assertFalse(result["execution_allowed"])
        self.assertFalse(result["commit_allowed"])
        self.assertFalse(result["push_allowed"])
        self.assertFalse(result["dataset_acquisition_allowed"])
        self.assertFalse(result["training_allowed"])
        self.assertTrue(result["planned_outputs_absent"])

    def test_network_surface_is_exactly_one_capability_gated_module(self):
        result = audit()
        surface = result["network_surface"]
        self.assertEqual(surface["urllib_request_imports"], [HTTP_TRANSPORT])
        self.assertEqual(surface["build_opener_calls"], [HTTP_TRANSPORT])
        self.assertEqual(surface["forbidden_clients"], [])

    def test_pdf_runtime_and_git_lineage_are_pinned(self):
        result = audit()
        self.assertIn(result["ahead"], {0, 1})
        self.assertEqual(result["behind"], 0)
        self.assertEqual(result["pdf_runtime"]["pypdf"], "6.10.0")
        self.assertEqual(result["pdf_runtime"]["pdfplumber"], "0.11.9")
        self.assertTrue(result["pdf_runtime"]["pdftoppm_exists"])
        self.assertTrue(result["pdf_runtime"]["pdfinfo_exists"])


if __name__ == "__main__":
    unittest.main()
