import unittest

from scripts.run_current_test_suite_v9 import LIFECYCLE_REPLACEMENTS as V9
from scripts.run_current_test_suite_v10 import LIFECYCLE_REPLACEMENTS as V10


class CurrentSuiteV10Tests(unittest.TestCase):
    def test_mapping_adds_exact_two_postexecution_replacements(self):
        self.assertEqual((len(V9), len(V10), len(set(V10) - set(V9))), (32, 34, 2))
        self.assertEqual(len(set(V10.values())), 34)


if __name__ == "__main__":
    unittest.main()
