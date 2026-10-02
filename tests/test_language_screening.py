import gzip
import unittest

from src.isi.normalization.language_screening import screen_html_language


class LanguageScreeningTests(unittest.TestCase):
    def test_declared_english_is_routing_only_and_scripts_are_excluded(self):
        html = b"<html lang='en'><body>This is our investment page for you.</body><script>espagnol</script></html>"
        screening, text = screen_html_language(html)
        self.assertEqual(screening["automatic_language_bucket"], "ENGLISH")
        self.assertEqual(screening["automatic_language_hint"], "en")
        self.assertNotIn("espagnol", text)
        self.assertTrue(screening["manual_confirmation_required"])
        self.assertFalse(screening["ground_truth_label_created"])
        self.assertFalse(screening["model_feature_allowed"])

    def test_declared_spanish_routes_non_english(self):
        screening, _ = screen_html_language(
            b"<html lang='es-MX'><body>La inversion es para una persona.</body></html>"
        )
        self.assertEqual(screening["automatic_language_bucket"], "NON_ENGLISH")
        self.assertEqual(screening["automatic_language_hint"], "es")

    def test_ambiguous_short_text_is_not_forced_to_a_language(self):
        screening, _ = screen_html_language(b"<html><body>Alpha Capital</body></html>")
        self.assertEqual(screening["automatic_language_bucket"], "MIXED_OR_UNDETERMINED")

    def test_gzip_transport_is_profiled_without_mutation(self):
        raw = gzip.compress(b"<html lang='en'><body>The investment is for you and your future.</body></html>")
        screening, _ = screen_html_language(raw)
        self.assertEqual(screening["transport_decoding"], "gzip")
        self.assertEqual(screening["automatic_language_bucket"], "ENGLISH")


if __name__ == "__main__":
    unittest.main()
