import unittest
from scripts.run_current_test_suite_v5 import LIFECYCLE_REPLACEMENTS as V5
from scripts.run_current_test_suite_v6 import LIFECYCLE_REPLACEMENTS as V6
class CurrentTestSuiteV6Tests(unittest.TestCase):
 def test_v6_adds_five_transitions(self): self.assertEqual((len(V5),len(V6),len(set(V6)-set(V5))),(12,17,5))
 def test_replacements_unique(self): self.assertEqual(len(set(V6.values())),17)
if __name__=='__main__':unittest.main()
