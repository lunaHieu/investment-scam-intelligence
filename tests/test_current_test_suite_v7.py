import unittest
from scripts.run_current_test_suite_v6 import LIFECYCLE_REPLACEMENTS as A
from scripts.run_current_test_suite_v7 import LIFECYCLE_REPLACEMENTS as B
class SuiteV7Tests(unittest.TestCase):
 def test_mapping(self):self.assertEqual((len(A),len(B),len(set(B)-set(A))),(17,19,2));self.assertEqual(len(set(B.values())),19)
if __name__=='__main__':unittest.main()
