import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from compare_mendeley_prediction_errors import exact_mcnemar_p_value


class PredictionComparisonTests(unittest.TestCase):
    def test_exact_mcnemar_equal_discordance_is_not_significant(self):
        self.assertEqual(exact_mcnemar_p_value(10, 10), 1.0)

    def test_exact_mcnemar_one_sided_discordance_is_significant(self):
        self.assertLess(exact_mcnemar_p_value(0, 10), 0.05)

    def test_exact_mcnemar_no_discordance(self):
        self.assertEqual(exact_mcnemar_p_value(0, 0), 1.0)


if __name__ == "__main__":
    unittest.main()
