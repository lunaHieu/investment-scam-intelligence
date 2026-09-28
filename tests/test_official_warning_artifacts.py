import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.isi.curation.official_warning_artifacts import analyze_warning_capture


class OfficialWarningArtifactTests(unittest.TestCase):
    def test_warning_text_remains_evidence_and_linked_assets_are_only_candidates(self):
        candidate = {
            "candidate_id": "EXTCAP_CONF_001",
            "candidate_host": "offer.example",
            "entity_name_keys": ["Example Offer"],
            "official_reference": {"url": "https://regulator.example/warning"},
        }
        html = b"""<!doctype html><html><body>
        <p>Warning about Example Offer at offer.example.</p>
        <a href='/files/example-offer.pdf'>Evidence</a>
        <img src='/media/example-offer-screenshot.png' alt='Example Offer screenshot'>
        </body></html>"""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "warning.html"
            path.write_bytes(html)
            result = analyze_warning_capture(candidate=candidate, capture_path=path)
        self.assertTrue(result["candidate_host_in_visible_text"])
        self.assertEqual(result["document_attachment_count"], 1)
        self.assertEqual(result["identity_relevant_document_count"], 1)
        self.assertEqual(result["identity_relevant_media_count"], 1)
        self.assertEqual(result["follow_up_asset_count"], 2)
        self.assertFalse(result["warning_page_as_model_input_allowed"])
        self.assertFalse(result["observed_solicitation_artifact_found"])

    def test_generic_logo_is_not_an_identity_relevant_media_asset(self):
        candidate = {
            "candidate_id": "EXTCAP_CONF_001",
            "candidate_host": "offer.example",
            "entity_name_keys": ["Example Offer"],
            "official_reference": {"url": "https://regulator.example/warning"},
        }
        html = b"<html><body><img src='/assets/example-logo.png' alt='Example logo'></body></html>"
        with TemporaryDirectory() as directory:
            path = Path(directory) / "warning.html"
            path.write_bytes(html)
            result = analyze_warning_capture(candidate=candidate, capture_path=path)
        self.assertEqual(result["identity_relevant_media_count"], 0)

    def test_generic_regulator_document_is_not_a_follow_up_asset(self):
        candidate = {
            "candidate_id": "EXTCAP_CONF_001",
            "candidate_host": "offer.example",
            "entity_name_keys": ["Example Offer"],
            "official_reference": {"url": "https://regulator.example/warning"},
        }
        html = b"<html><body><a href='/media/regulator-a-portrait.pdf'>About the regulator</a></body></html>"
        with TemporaryDirectory() as directory:
            path = Path(directory) / "warning.html"
            path.write_bytes(html)
            result = analyze_warning_capture(candidate=candidate, capture_path=path)
        self.assertEqual(result["document_attachment_count"], 1)
        self.assertEqual(result["identity_relevant_document_count"], 0)
        self.assertEqual(result["follow_up_asset_count"], 0)


if __name__ == "__main__":
    unittest.main()
