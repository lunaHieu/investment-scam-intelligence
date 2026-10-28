import unittest

from scripts.run_current_test_suite_v4 import LIFECYCLE_REPLACEMENTS as V4
from scripts.run_current_test_suite_v5 import LIFECYCLE_REPLACEMENTS as V5


class CurrentTestSuiteV5Tests(unittest.TestCase):
    def test_v5_adds_exactly_one_consumed_continuation_transition(self):
        self.assertEqual(len(V4), 11)
        self.assertEqual(len(V5), 12)
        self.assertEqual(len(set(V5) - set(V4)), 1)

    def test_every_exclusion_has_unique_replacement(self):
        self.assertEqual(len(set(V5.values())), 12)
        added = set(V5.values()) - set(V4.values())
        self.assertTrue(all("test_current_artifact_lifecycle_v5" in value for value in added))


if __name__ == "__main__":
    unittest.main()
