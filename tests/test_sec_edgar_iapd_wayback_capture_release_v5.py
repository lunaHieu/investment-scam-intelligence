import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from scripts.build_sec_edgar_iapd_wayback_capture_plan_v5 import build_plan
from scripts.build_sec_edgar_iapd_wayback_capture_release_v5 import build_release, parse_time
from scripts.execute_sec_edgar_iapd_wayback_capture_v1 import validate_release as executor_validate_release
from scripts.verify_sec_edgar_iapd_wayback_capture_plan_v5 import verify as verify_plan
from scripts.verify_sec_edgar_iapd_wayback_capture_release_v5 import verify
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file
from tests.test_sec_edgar_iapd_wayback_capture_plan_v5 import write_v8_fixture


class SecEdgarIapdWaybackCaptureReleaseV5Tests(unittest.TestCase):
    def make_plan(self, directory: Path) -> tuple[Path, Path, str]:
        availability_release, availability_path, availability_qa = write_v8_fixture(directory)
        plan = build_plan(
            release_path=availability_release, availability_path=availability_path,
            qa_path=availability_qa, raw_root=directory / "raw",
            capture_date="2026-10-20",
        )
        plan_path = directory / "capture_plan_v5.json"
        plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        plan_qa = verify_plan(plan_path, sha256_file(plan_path))
        plan_qa_path = directory / "capture_plan_qa_v5.json"
        plan_qa_path.write_text(json.dumps(plan_qa, indent=2) + "\n", encoding="utf-8")
        return plan_path, plan_qa_path, plan["availability_result"]["created_at"]

    def make_release(self, directory: Path) -> tuple[Path, Path, Path, str]:
        plan_path, plan_qa_path, availability_created_at = self.make_plan(directory)
        availability_time = parse_time(availability_created_at)
        not_before = (availability_time + timedelta(seconds=86400)).isoformat()
        release = build_release(
            plan_path=plan_path, qa_path=plan_qa_path, not_before=not_before,
            report_path=directory / "capture_report.json",
            created_at=(availability_time + timedelta(hours=1)).isoformat(),
        )
        release_path = directory / "capture_release_v5.json"
        release_path.write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
        return release_path, plan_path, directory / "capture_report.json", not_before

    def test_exact_24_hour_boundary_passes_independent_v5_verifier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            release_path, _, _, not_before = self.make_release(Path(tmp))
            result = verify(release_path)
        self.assertEqual(result["status"], "PASS_ARCHIVE_ONLY_CAPTURE_RELEASE")
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["checks"]["availability_generation"], "v8")
        self.assertEqual(result["checks"]["source_candidate_count"], 115)
        self.assertEqual(result["checks"]["minimum_cooldown_seconds"], 86400)
        self.assertEqual(result["checks"]["not_before"], not_before)
        self.assertTrue(result["checks"]["archive_host_only"])
        self.assertFalse(result["checks"]["output_overwrite_allowed"])

    def test_builder_rejects_gate_one_second_before_24_hours(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            plan_path, plan_qa_path, availability_created_at = self.make_plan(directory)
            availability_time = parse_time(availability_created_at)
            with self.assertRaisesRegex(ValueError, "less than 24 hours"):
                build_release(
                    plan_path=plan_path, qa_path=plan_qa_path,
                    not_before=(availability_time + timedelta(seconds=86399)).isoformat(),
                    report_path=directory / "capture_report.json",
                    created_at=(availability_time + timedelta(hours=1)).isoformat(),
                )

    def test_builder_rejects_nonpassing_plan_qa(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            plan_path, plan_qa_path, availability_created_at = self.make_plan(directory)
            qa = json.loads(plan_qa_path.read_text(encoding="utf-8"))
            qa["status"] = "FAIL"
            plan_qa_path.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
            availability_time = parse_time(availability_created_at)
            with self.assertRaisesRegex(ValueError, "did not pass"):
                build_release(
                    plan_path=plan_path, qa_path=plan_qa_path,
                    not_before=(availability_time + timedelta(days=1)).isoformat(),
                    report_path=directory / "capture_report.json",
                    created_at=(availability_time + timedelta(hours=1)).isoformat(),
                )

    def test_tampered_cooldown_fails_and_v5_remains_executor_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            release_path, _, _, _ = self.make_release(directory)
            release_qa = verify(release_path)
            release_qa_path = directory / "capture_release_qa_v5.json"
            release_qa_path.write_text(json.dumps(release_qa, indent=2) + "\n", encoding="utf-8")
            validated_release, validated_plan = executor_validate_release(release_path, release_qa_path)
            self.assertEqual(validated_release["tooling_version"], "v5")
            self.assertEqual(validated_plan["availability_generation"], "v8")

            release = json.loads(release_path.read_text(encoding="utf-8"))
            availability_time = parse_time(release["inputs"]["final_availability_result"]["created_at"])
            too_early = (availability_time + timedelta(seconds=86399)).isoformat()
            release["execution_contract"]["not_before"] = too_early
            release["cooldown_contract"]["not_before"] = too_early
            release_path.write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
            result = verify(release_path)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("less than 24 hours" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
