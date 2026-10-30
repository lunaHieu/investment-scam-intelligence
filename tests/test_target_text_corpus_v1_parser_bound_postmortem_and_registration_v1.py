import unittest

from scripts.verify_target_text_corpus_v1_parser_bound_postmortem_and_registration_v1 import (
    PASS_STATUS,
    verify,
)


class ParserBoundPostmortemAndRegistrationV1Tests(unittest.TestCase):
    def test_postmortem_is_bounded_and_exact_two_successes_are_registered(self):
        result = verify()
        self.assertEqual(result["status"], PASS_STATUS, result["errors"])
        self.assertEqual(result["checks"]["postmortem_resources"], ["PBC05", "PBC08"])
        self.assertEqual(result["checks"]["registered_success_resources"], ["PBC06", "PBC07"])
        self.assertEqual(result["checks"]["pbc05_confirmed_stage"], "SECTION_EXTRACTION")
        self.assertFalse(result["checks"]["pbc08_exact_reason_recoverable"])
        self.assertEqual(result["checks"]["dataset_rows_admitted"], 0)
        self.assertEqual(result["checks"]["labels_created"], 0)
        self.assertFalse(result["decision"]["network_execution_allowed"])
        self.assertFalse(result["decision"]["training_allowed"])
        self.assertEqual(result["errors"], [])


if __name__ == "__main__":
    unittest.main()
