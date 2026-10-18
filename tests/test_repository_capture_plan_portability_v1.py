import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from scripts.build_sec_edgar_iapd_wayback_capture_plan_v4 import build_plan
from scripts.build_sec_edgar_iapd_wayback_capture_release_v4 import build_release, parse_time
from scripts.verify_sec_edgar_iapd_wayback_capture_plan_v4 import verify
from scripts.verify_sec_edgar_iapd_wayback_capture_release_v4 import verify as verify_release
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file
from tests.test_sec_edgar_iapd_wayback_capture_plan_v4 import write_v7_fixture


class RepositoryCapturePlanPortabilityV1Tests(unittest.TestCase):
    @staticmethod
    def canonical_fixture(directory: Path) -> tuple[Path, Path, Path]:
        release_path, result_path, qa_path = write_v7_fixture(directory)
        release = json.loads(release_path.read_text(encoding="utf-8"))
        source_path = Path(release["inputs"]["availability_plan"]["path"])
        release["inputs"]["availability_plan"]["path"] = str(source_path.resolve())
        release_path.write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")

        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["release_sha256"] = sha256_file(release_path)
        result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

        qa = json.loads(qa_path.read_text(encoding="utf-8"))
        qa["inputs"]["v7_sha256"] = sha256_file(result_path)
        qa_path.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
        return release_path, result_path, qa_path

    def build_verified_plan(self, directory: Path) -> tuple[Path, Path, dict]:
        release_path, result_path, qa_path = self.canonical_fixture(directory)
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
        return plan_path, result_path, checked

    def test_v7_capture_plan_round_trip_is_path_portable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, _, checked = self.build_verified_plan(Path(tmp))
        self.assertEqual(
            checked["status"],
            "PASS_EXACT_AVAILABLE_SNAPSHOT_PLAN_REGISTER_BEFORE_EXECUTION",
            checked["errors"],
        )

    def test_v7_capture_release_round_trip_is_path_portable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            plan_path, _, plan_qa = self.build_verified_plan(directory)
            self.assertEqual(plan_qa["errors"], [])
            plan_qa_path = directory / "capture_plan_qa_v4.json"
            plan_qa_path.write_text(json.dumps(plan_qa, indent=2) + "\n", encoding="utf-8")

            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            availability_time = parse_time(plan["availability_result"]["created_at"])
            release = build_release(
                plan_path=plan_path,
                qa_path=plan_qa_path,
                not_before=(availability_time + timedelta(days=1)).isoformat(),
                report_path=directory / "capture_report.json",
                created_at=(availability_time + timedelta(hours=1)).isoformat(),
            )
            release_path = directory / "capture_release_v4.json"
            release_path.write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
            checked = verify_release(release_path)

        self.assertEqual(checked["status"], "PASS_ARCHIVE_ONLY_CAPTURE_RELEASE", checked["errors"])


if __name__ == "__main__":
    unittest.main()
