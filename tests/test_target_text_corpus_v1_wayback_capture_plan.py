import tempfile
import unittest
from pathlib import Path

from scripts.build_target_text_corpus_v1_wayback_capture_plan import build_plan
from scripts.capture_target_text_corpus_v1_wayback_plan import validate_plan
from scripts.query_target_text_corpus_v1_wayback_availability import sha256_file


DATA = Path(r"D:\nckh 2026-2027\ISI_Data")
PILOT = DATA / "curated" / "target_text_corpus_v1_schema_review_pilot"


class TargetTextCorpusWaybackCapturePlanTests(unittest.TestCase):
    def test_build_plan_contains_exact_available_population(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan = build_plan(
                availability_path=PILOT / "wayback_availability_report_v2.json",
                qa_path=PILOT / "wayback_availability_independent_qa_v2.json",
                raw_root=Path(directory),
                capture_date="2026-10-03",
            )
        self.assertEqual(plan["planned_capture_count"], 29)
        self.assertEqual(sum(plan["planned_by_channel"].values()), 29)
        self.assertTrue(all("id_/" in row["requested_archive_url"] for row in plan["results"]))

    def test_frozen_plan_hash_and_population_validate(self) -> None:
        plan_path = PILOT / "wayback_capture_plan_v1.json"
        plan = validate_plan(plan_path, sha256_file(plan_path))
        self.assertEqual(plan["planned_capture_count"], 29)


if __name__ == "__main__":
    unittest.main()
