import unittest
from pathlib import Path

from scripts.retry_target_text_corpus_v1_wayback_availability import (
    load_json,
    retry_candidate_ids,
    validate_protocol,
)


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "configs" / "target_text_corpus_v1_wayback_availability_retry_v2.json"


class TargetTextCorpusWaybackAvailabilityRetryTests(unittest.TestCase):
    def test_frozen_retry_protocol_passes(self) -> None:
        result = validate_protocol(PROTOCOL)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["retry_candidate_count"], 31)

    def test_only_unresolved_rows_are_selected(self) -> None:
        protocol = load_json(PROTOCOL)
        report_path = Path(protocol["basis"][2]["path"])
        report = load_json(report_path)
        retry_ids = retry_candidate_ids(report)
        self.assertEqual(len(retry_ids), 31)
        resolved_ids = {
            row["candidate_id"] for row in report["results"] if row["error"] is None
        }
        self.assertTrue(resolved_ids.isdisjoint(retry_ids))


if __name__ == "__main__":
    unittest.main()
