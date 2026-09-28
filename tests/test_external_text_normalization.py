import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.isi.normalization.external_text import (
    capture_to_draft_record,
    choose_capture_url,
    extract_visible_text,
    identity_token_check,
)


class ExternalTextNormalizationTests(unittest.TestCase):
    def test_visible_text_excludes_script_and_keeps_canonical_url(self):
        html = b"""
        <html><head><link rel="canonical" href="https://www.firm.example/about">
        <style>hidden style</style><script>hidden script</script></head>
        <body><h1>Firm Example</h1><p>Independent investment advice.</p></body></html>
        """
        text, canonical = extract_visible_text(html)
        self.assertEqual(text, "Firm Example Independent investment advice.")
        self.assertEqual(canonical, ["https://www.firm.example/about"])

    def test_visible_text_collapses_exact_repeated_long_responsive_blocks(self):
        repeated = "This is a long responsive content block repeated for mobile and desktop."
        html = f"<main><p>{repeated}</p><p>{repeated}</p></main>".encode()
        text, _ = extract_visible_text(html)
        self.assertEqual(text, repeated)

    def test_identity_check_is_lexical_and_conservative(self):
        result = identity_token_check(
            ["Greenlea Lane Capital Management LLC"],
            "Welcome to Greenlea Lane Capital Management.",
        )
        self.assertTrue(result["any_full_token_match"])
        self.assertIn("human identity reconciliation", result["interpretation"])

    def test_capture_draft_remains_uncertain_and_unreviewed(self):
        candidate = {
            "candidate_id": "EXTCAP_LEGIT_001",
            "candidate_host": "firm.example",
            "source_record_id": "123",
            "entity_name_keys": ["Firm Example LLC"],
            "official_reference": {"url": "https://adviserinfo.sec.gov/firm/summary/123"},
        }
        with TemporaryDirectory() as temp_dir:
            capture = Path(temp_dir) / "capture.html"
            capture.write_text(
                '<link rel="canonical" href="https://www.firm.example/">'
                "<h1>Firm Example</h1><p>Investment advisory services.</p>",
                encoding="utf-8",
            )
            record, profile = capture_to_draft_record(
                candidate=candidate,
                capture_path=capture,
                capture_relative_path="external/capture.html",
                content_observed_at="2026-09-24T00:00:00+07:00",
                collection_date="2026-09-24",
            )
        self.assertEqual(record["ground_truth_status"], "UNCERTAIN")
        self.assertEqual(record["label_confidence"], "LOW")
        self.assertEqual(record["review_status"], "IN_REVIEW")
        self.assertFalse(record["evidence"][0]["reviewed"])
        self.assertEqual(record["evidence"][0]["supports"], ["IDENTITY"])
        self.assertFalse(profile["external_evaluation_eligible"])
        self.assertEqual(
            choose_capture_url("firm.example", ["https://malicious.example/"]),
            "https://firm.example/",
        )


if __name__ == "__main__":
    unittest.main()
