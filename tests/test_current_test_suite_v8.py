import unittest

from scripts.run_current_test_suite_v7 import LIFECYCLE_REPLACEMENTS as V7
from scripts.run_current_test_suite_v8 import LIFECYCLE_REPLACEMENTS as V8


class CurrentSuiteV8Tests(unittest.TestCase):
    def test_mapping_adds_exact_eight_postexecution_replacements(self):
        self.assertEqual((len(V7), len(V8), len(set(V8) - set(V7))), (19, 27, 8))
        self.assertEqual(len(set(V8.values())), 27)


if __name__ == "__main__":
    unittest.main()
