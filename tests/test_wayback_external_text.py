import gzip
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.isi.normalization.wayback_external_text import (
    decode_archived_payload,
    screen_archived_capture,
)


def candidate(entity="Example Capital"):
    return {
        "candidate_id": "EXTCAP_CONF_001",
        "candidate_host": "example.test",
        "entity_name_keys": [entity],
    }


class WaybackExternalTextTests(unittest.TestCase):
    def test_plain_payload_is_unchanged(self):
        raw = b"<html><body>Example Capital trading account deposit</body></html>"
        decoded, method = decode_archived_payload(raw)
        self.assertEqual(decoded, raw)
        self.assertEqual(method, "identity")

    def test_gzip_payload_is_decoded_in_memory(self):
        html = b"<html><body>Example Capital trading account deposit</body></html>"
        decoded, method = decode_archived_payload(gzip.compress(html))
        self.assertEqual(decoded, html)
        self.assertEqual(method, "gzip")

    def test_identity_and_solicitation_text_is_routed_to_human_review(self):
        body = "Example Capital offers a funded trading account. Deposit to trade markets. " * 8
        with TemporaryDirectory() as directory:
            path = Path(directory) / "capture.html"
            path.write_bytes(gzip.compress(f"<html><body>{body}</body></html>".encode()))
            profile, _, _ = screen_archived_capture(candidate=candidate(), capture_path=path)
        self.assertEqual(profile["transport_decoding"], "gzip")
        self.assertEqual(profile["screening_decision"], "REVIEWABLE_OBSERVED_TEXT")
        self.assertFalse(profile["external_evaluation_eligible"])
        self.assertFalse(profile["label_created"])

    def test_parked_domain_is_rejected_even_when_identity_appears(self):
        body = "Example Capital - This domain may be for sale. Namecheap domain parking. " * 8
        with TemporaryDirectory() as directory:
            path = Path(directory) / "capture.html"
            path.write_text(f"<html><body>{body}</body></html>", encoding="utf-8")
            profile, _, _ = screen_archived_capture(candidate=candidate(), capture_path=path)
        self.assertEqual(profile["screening_decision"], "REJECT_PARKED_DOMAIN")

    def test_repurposed_domain_without_identity_is_rejected(self):
        body = "Unrelated web development services and software consulting. " * 8
        with TemporaryDirectory() as directory:
            path = Path(directory) / "capture.html"
            path.write_text(f"<html><body>{body}</body></html>", encoding="utf-8")
            profile, _, _ = screen_archived_capture(candidate=candidate(), capture_path=path)
        self.assertEqual(
            profile["screening_decision"],
            "REJECT_IDENTITY_MISMATCH_OR_REPURPOSED_DOMAIN",
        )


if __name__ == "__main__":
    unittest.main()
