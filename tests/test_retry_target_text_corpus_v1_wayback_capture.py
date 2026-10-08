import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.retry_target_text_corpus_v1_wayback_capture import (
    unresolved_candidate_ids,
    validate_protocol,
)
from scripts.query_target_text_corpus_v1_wayback_availability import load_json


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "configs" / "target_text_corpus_v1_wayback_capture_retry_v2.json"


class TargetTextCorpusWaybackCaptureRetryTests(unittest.TestCase):
    def test_retry_protocol_passes_after_cooldown(self) -> None:
        result = validate_protocol(
            PROTOCOL,
            now=datetime(2026, 10, 8, 8, 30, tzinfo=timezone.utc),
        )
        self.assertTrue(result["valid"], result["errors"])
        self.assertTrue(result["cooldown_ready"])
        self.assertEqual(result["retry_candidate_count"], 29)

    def test_cooldown_fails_closed(self) -> None:
        result = validate_protocol(
            PROTOCOL,
            now=datetime(2026, 10, 3, 2, 0, tzinfo=timezone.utc),
        )
        self.assertFalse(result["valid"])
        self.assertIn("Required capture retry cooldown has not elapsed", result["errors"])

    def test_all_prior_rows_are_unresolved(self) -> None:
        protocol = load_json(PROTOCOL)
        prior = load_json(Path(protocol["basis"][2]["path"]))
        self.assertEqual(len(unresolved_candidate_ids(prior)), 29)


if __name__ == "__main__":
    unittest.main()
