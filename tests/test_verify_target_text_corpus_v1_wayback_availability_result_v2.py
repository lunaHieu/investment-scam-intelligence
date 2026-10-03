import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_wayback_availability_result_v2 import (
    verify,
    verify_registry,
)


DATA = Path(r"D:\nckh 2026-2027\ISI_Data")
PILOT = DATA / "curated" / "target_text_corpus_v1_schema_review_pilot"


class WaybackAvailabilityResultV2Tests(unittest.TestCase):
    def test_complete_result_passes_independent_verification(self) -> None:
        result = verify(
            queue_path=PILOT / "candidate_queue_v1.jsonl",
            v1_path=PILOT / "wayback_availability_report_v1.json",
            v2_path=PILOT / "wayback_availability_report_v2.json",
        )
        self.assertFalse(result["errors"], result["errors"])
        self.assertEqual(result["checks"]["available_snapshot_count"], 29)
        self.assertEqual(result["checks"]["unavailable_snapshot_count"], 11)
        self.assertFalse(result["decision"]["candidate_capture_allowed"])

    def test_frozen_result_registry_passes(self) -> None:
        registry = (
            Path(__file__).resolve().parents[1]
            / "registry"
            / "analyses"
            / "target_text_corpus_v1_wayback_availability_result_v2.json"
        )
        result = verify_registry(registry)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["available_snapshot_count"], 29)


if __name__ == "__main__":
    unittest.main()
