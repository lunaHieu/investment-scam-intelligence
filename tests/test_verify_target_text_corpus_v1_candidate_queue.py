import unittest

from scripts.verify_target_text_corpus_v1_candidate_queue import (
    independent_expected_selection,
    normalized_entity,
)


class VerifyTargetTextCorpusCandidateQueueTests(unittest.TestCase):
    def test_normalized_entity_is_case_and_punctuation_stable(self):
        self.assertEqual(normalized_entity("Alpha-Ridge, LLC"), "alpha ridge llc")

    def test_independent_selection_deduplicates_host_before_ranking(self):
        channels = {
            "CONFIRMED_REGULATOR_LINKED_WEBSITE": [
                {
                    "source_id": "iosco_i_scan",
                    "source_record_id": "1",
                    "normalized_host": "one.example",
                    "entity_name_from_reference": "One",
                },
                {
                    "source_id": "iosco_i_scan",
                    "source_record_id": "2",
                    "normalized_host": "one.example",
                    "entity_name_from_reference": "Other",
                },
            ]
        }
        result = independent_expected_selection(channels, "seed", quota=1)
        self.assertEqual(len(result["CONFIRMED_REGULATOR_LINKED_WEBSITE"]), 1)


if __name__ == "__main__":
    unittest.main()
