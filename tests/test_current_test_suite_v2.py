import unittest

from scripts.run_current_test_suite_v1 import LIFECYCLE_REPLACEMENTS as V1
from scripts.run_current_test_suite_v2 import LIFECYCLE_REPLACEMENTS as V2


class CurrentTestSuiteV2Tests(unittest.TestCase):
    def test_v2_adds_exactly_one_consumed_canary_transition(self) -> None:
        self.assertEqual(len(V1), 5)
        self.assertEqual(len(V2), 6)
        self.assertEqual(set(V2) - set(V1), {
            "test_target_text_corpus_v1_ready_channel_cdx_canary_v1.ReadyChannelCdxCanaryV1Tests.test_real_release_passes_independent_verification"
        })

    def test_every_exclusion_has_a_unique_replacement(self) -> None:
        self.assertEqual(len(set(V2.values())), 6)
        self.assertIn("test_current_artifact_lifecycle_v2", list(set(V2.values()) - set(V1.values()))[0])


if __name__ == "__main__":
    unittest.main()
