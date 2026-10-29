import unittest

from scripts.dry_run_target_text_corpus_v1_parser_bound_content_v1 import (
    run_dry_run,
    synthetic_payload,
)


class ParserBoundEndToEndDryRunV1Tests(unittest.TestCase):
    def test_all_eight_synthetic_payloads_exist(self):
        for number in range(1, 9):
            self.assertGreater(len(synthetic_payload(f"PBC{number:02}")), 0)

    def test_end_to_end_dry_run_passes_without_network_or_artifact(self):
        result = run_dry_run()
        self.assertEqual(result["status"], "PASS_SYNTHETIC_END_TO_END_DRY_RUN")
        self.assertEqual(result["resources"], 8)
        self.assertEqual(result["success"], 8)
        self.assertEqual(result["journal_events"], 10)
        self.assertEqual(result["network_operations"], 0)
        self.assertFalse(result["real_result_created"])
        self.assertFalse(result["evidence_acceptance_allowed"])
        self.assertFalse(result["dataset_acquisition_allowed"])
        self.assertFalse(result["training_allowed"])


if __name__ == "__main__":
    unittest.main()
