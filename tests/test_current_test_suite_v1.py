import unittest

from scripts.run_current_test_suite_v1 import LIFECYCLE_REPLACEMENTS


class CurrentTestSuiteV1Tests(unittest.TestCase):
    def test_exclusion_set_is_exact_and_bounded(self) -> None:
        self.assertEqual(len(LIFECYCLE_REPLACEMENTS), 5)
        self.assertEqual(len(set(LIFECYCLE_REPLACEMENTS.values())), 5)

    def test_every_exclusion_has_an_explicit_postexecution_replacement(self) -> None:
        for historical, replacement in LIFECYCLE_REPLACEMENTS.items():
            self.assertIn("test_", historical)
            self.assertIn("test_current_artifact_lifecycle_v1", replacement)


if __name__ == "__main__":
    unittest.main()
