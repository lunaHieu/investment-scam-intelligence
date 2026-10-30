import unittest

from scripts.execute_target_text_corpus_v1_parser_bound_content_diagnostic_v1 import execution_preflight
from scripts.verify_target_text_corpus_v1_parser_bound_content_diagnostic_result_v1 import (
    DEFAULT_RESULT,
    verify_result,
)


class CurrentArtifactLifecycleV10Tests(unittest.TestCase):
    def test_diagnostic_result_is_verified_with_exact_two_parser_rejections(self):
        result = verify_result(DEFAULT_RESULT)
        self.assertEqual(result["status"], "PASS_PARSER_BOUND_DIAGNOSTIC_RESULT_VERIFIED")
        self.assertEqual(
            (result["checks"]["resources"], result["checks"]["success"], result["checks"]["parser_rejected"]),
            (2, 0, 2),
        )

    def test_completed_diagnostic_result_closes_executor_preflight(self):
        preflight = execution_preflight()
        self.assertFalse(preflight["execution_allowed"])
        self.assertTrue(DEFAULT_RESULT.is_file())
        self.assertFalse(preflight["network_operations"])


if __name__ == "__main__":
    unittest.main()
