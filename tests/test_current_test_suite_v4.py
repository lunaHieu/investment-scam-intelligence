import unittest

from scripts.run_current_test_suite_v3 import LIFECYCLE_REPLACEMENTS as V3
from scripts.run_current_test_suite_v4 import LIFECYCLE_REPLACEMENTS as V4


class CurrentTestSuiteV4Tests(unittest.TestCase):
    def test_v4_adds_exactly_one_consumed_capture_transition(self) -> None:
        self.assertEqual(len(V3), 7)
        self.assertEqual(len(V4), 11)
        self.assertEqual(len(set(V4) - set(V3)), 4)

    def test_every_exclusion_has_unique_replacement(self) -> None:
        self.assertEqual(len(set(V4.values())), 11)
        self.assertTrue(all("test_current_artifact_lifecycle_v4" in value for value in set(V4.values()) - set(V3.values())))


if __name__ == "__main__":
    unittest.main()
