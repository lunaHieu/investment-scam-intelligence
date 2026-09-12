import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from extract_crimson_url_features import extract_features, shannon_entropy


class CrimsonUrlFeatureTests(unittest.TestCase):
    def test_domain_features_are_deterministic(self):
        first = extract_features("xn--exmple-cua123.test")
        second = extract_features("XN--EXMPLE-CUA123.TEST.")
        self.assertEqual(first, second)
        self.assertEqual(first["label_count"], 2)
        self.assertEqual(first["punycode_label_count"], 1)
        self.assertGreater(first["digit_count"], 0)

    def test_ip_literal_is_detected(self):
        self.assertTrue(extract_features("192.0.2.10")["is_ip_literal"])

    def test_entropy_for_repeated_character_is_zero(self):
        self.assertEqual(shannon_entropy("aaaa"), 0.0)


if __name__ == "__main__":
    unittest.main()
