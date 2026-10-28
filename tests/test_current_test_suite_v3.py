import unittest

from scripts.run_current_test_suite_v2 import LIFECYCLE_REPLACEMENTS as V2
from scripts.run_current_test_suite_v3 import LIFECYCLE_REPLACEMENTS as V3


class CurrentTestSuiteV3Tests(unittest.TestCase):
    def test_v3_adds_exactly_one_consumed_bulk_transition(self) -> None:
        self.assertEqual(len(V2), 6)
        self.assertEqual(len(V3), 7)
        self.assertEqual(set(V3) - set(V2), {
            "test_target_text_corpus_v1_ready_channel_cdx_bulk_v1.ReadyChannelCdxBulkV1Tests.test_real_release_is_exact_unresolved_only_and_verified"
        })

    def test_every_exclusion_has_unique_replacement(self) -> None:
        self.assertEqual(len(set(V3.values())), 7)
        self.assertIn("test_current_artifact_lifecycle_v3", list(set(V3.values()) - set(V2.values()))[0])


if __name__ == "__main__":
    unittest.main()
