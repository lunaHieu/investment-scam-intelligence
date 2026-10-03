import unittest
from pathlib import Path

from scripts.query_target_text_corpus_v1_wayback_availability import sha256_file
from scripts.verify_target_text_corpus_v1_wayback_capture_plan_v1 import verify


PLAN = Path(
    r"D:\nckh 2026-2027\ISI_Data\curated\target_text_corpus_v1_schema_review_pilot"
) / "wayback_capture_plan_v1.json"


class TargetTextCorpusWaybackCapturePlanVerifierTests(unittest.TestCase):
    def test_frozen_capture_plan_passes(self) -> None:
        result = verify(PLAN, sha256_file(PLAN))
        self.assertFalse(result["errors"], result["errors"])
        self.assertEqual(result["checks"]["planned_capture_count"], 29)
        self.assertTrue(result["checks"]["all_and_only_available_candidates_planned"])
        self.assertFalse(result["decision"]["live_candidate_domain_access_allowed"])


if __name__ == "__main__":
    unittest.main()
