import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_sec_edgar_iapd_wayback_capture_plan_v4 import build_plan
from scripts.verify_sec_edgar_iapd_wayback_capture_plan_v4 import verify
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file
from tests.test_sec_edgar_iapd_wayback_capture_plan_v4 import write_v7_fixture


class RepositoryCapturePlanPortabilityV1Tests(unittest.TestCase):
    def test_v7_capture_plan_round_trip_is_path_portable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            release_path, result_path, qa_path = write_v7_fixture(directory)
            plan = build_plan(
                release_path=release_path,
                availability_path=result_path,
                qa_path=qa_path,
                raw_root=directory / "raw",
                capture_date="2026-10-20",
            )
            plan_path = directory / "capture_plan_v4.json"
            plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
            checked = verify(plan_path, sha256_file(plan_path))

        self.assertEqual(
            checked["status"],
            "PASS_EXACT_AVAILABLE_SNAPSHOT_PLAN_REGISTER_BEFORE_EXECUTION",
            checked["errors"],
        )


if __name__ == "__main__":
    unittest.main()
