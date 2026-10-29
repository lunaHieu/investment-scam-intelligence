import unittest

from scripts.verify_target_text_corpus_v1_sanitized_text_source_discovery_result_v1 import verify_result


class SanitizedTextSourceDiscoveryResultV1Tests(unittest.TestCase):
    def test_preliminary_result_verifies(self) -> None:
        result = verify_result()
        self.assertEqual(result["status"], "PASS_PRELIMINARY_RESULT_REQUIRES_SECOND_REVIEW")
        self.assertEqual(result["candidate_count"], 16)
        self.assertEqual(result["shortlist_count"], 6)


if __name__ == "__main__":
    unittest.main()
