import unittest

from scripts.verify_target_text_corpus_v1_parser_bound_content_supplemental_release_v1 import (
    PASS_STATUS,
    verify,
)


class ParserBoundContentSupplementalReleaseV1Tests(unittest.TestCase):
    def test_exact_supplemental_population_is_verified_but_execution_closed(self):
        result = verify()
        self.assertEqual(result["status"], PASS_STATUS, result["errors"])
        self.assertEqual(result["checks"]["resource_ids"], ["PBC05", "PBC06", "PBC07", "PBC08"])
        self.assertEqual(result["checks"]["maximum_get_requests"], 4)
        self.assertTrue(result["checks"]["continue_after_row_local_parser_failure"])
        self.assertFalse(result["decision"]["network_execution_allowed_now"])


if __name__ == "__main__":
    unittest.main()
