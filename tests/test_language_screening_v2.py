import unittest

from src.isi.normalization.language_screening_v2 import screen_html_language_v2


class LanguageScreeningV2Tests(unittest.TestCase):
    def test_zxx_is_non_decisive_and_english_text_routes_english(self):
        body = " ".join(
            ["the investment is for you and your account with our financial team"] * 10
        )
        screening, _ = screen_html_language_v2(
            f"<html lang='zxx'><body>{body}</body></html>".encode()
        )
        self.assertEqual(screening["automatic_language_bucket"], "ENGLISH")
        self.assertEqual(screening["non_decisive_declared_language_codes"], ["zxx"])

    def test_replacement_character_payload_is_blocked_before_language(self):
        body = ("\ufffd" * 20) + (" the investment is for you and your account" * 20)
        screening, _ = screen_html_language_v2(
            f"<html lang='en'><body>{body}</body></html>".encode()
        )
        self.assertEqual(
            screening["text_quality_state"], "UNREADABLE_DECODING_OR_BINARY_PAYLOAD"
        )
        self.assertEqual(
            screening["automatic_language_bucket"], "MIXED_OR_UNDETERMINED"
        )
        self.assertFalse(screening["manual_confirmation_required"])

    def test_tiny_page_is_insufficient(self):
        screening, _ = screen_html_language_v2(b"<html lang='en'><body>Visit us</body></html>")
        self.assertEqual(screening["text_quality_state"], "INSUFFICIENT_VISIBLE_TEXT")
        self.assertFalse(screening["manual_confirmation_required"])


if __name__ == "__main__":
    unittest.main()
