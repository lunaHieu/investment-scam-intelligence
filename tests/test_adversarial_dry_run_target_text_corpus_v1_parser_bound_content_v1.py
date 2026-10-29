import unittest

from scripts.adversarial_dry_run_target_text_corpus_v1_parser_bound_content_v1 import (
    SCENARIOS,
    run_matrix,
    run_scenario,
)


class ParserBoundAdversarialDryRunV1Tests(unittest.TestCase):
    def test_each_resource_fails_closed_independently(self):
        for target_id in SCENARIOS:
            with self.subTest(target_id=target_id):
                result = run_scenario(target_id)
                self.assertTrue(result["honest_failure_report_verified"])
                self.assertTrue(result["tampered_success_rejected"])
                self.assertEqual(result["journal_events"], 10)
                self.assertEqual(result["network_operations"], 0)
                self.assertFalse(result["temporary_artifacts_retained"])

    def test_complete_matrix_has_exact_coverage(self):
        result = run_matrix()
        self.assertEqual(result["status"], "PASS_ADVERSARIAL_FAILURE_MATRIX")
        self.assertEqual(result["scenarios"], 8)
        self.assertEqual(result["honest_failure_reports_verified"], 8)
        self.assertEqual(result["tampered_successes_rejected"], 8)
        self.assertEqual(result["journal_events"], 80)
        self.assertEqual(result["network_operations"], 0)
        self.assertFalse(result["temporary_artifacts_retained"])


if __name__ == "__main__":
    unittest.main()
