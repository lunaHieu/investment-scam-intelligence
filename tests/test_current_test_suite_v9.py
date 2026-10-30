import unittest

from scripts.run_current_test_suite_v8 import LIFECYCLE_REPLACEMENTS as V8
from scripts.run_current_test_suite_v9 import LIFECYCLE_REPLACEMENTS as V9


class CurrentSuiteV9Tests(unittest.TestCase):
    def test_mapping_adds_exact_five_postexecution_replacements(self):
        self.assertEqual((len(V8), len(V9), len(set(V9) - set(V8))), (27, 32, 5))
        self.assertEqual(len(set(V9.values())), 32)


if __name__ == "__main__":
    unittest.main()
