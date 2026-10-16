import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from scripts.build_sec_edgar_iapd_wayback_capture_plan_v2 import build_plan
from scripts.build_sec_edgar_iapd_wayback_capture_release_v2 import build_release, parse_time
from scripts.execute_sec_edgar_iapd_wayback_capture_v1 import validate_release as executor_validate_release
from scripts.verify_sec_edgar_iapd_wayback_capture_plan_v2 import verify as verify_plan
from scripts.verify_sec_edgar_iapd_wayback_capture_release_v2 import verify
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file
from tests.test_sec_edgar_iapd_wayback_capture_plan_v2 import write_fixture


class SecEdgarIapdWaybackCaptureReleaseV2Tests(unittest.TestCase):
    def make_plan(self, directory: Path) -> tuple[Path, Path, str]:
        availability_release, availability_path, availability_qa = write_fixture(directory, "v5")
        plan = build_plan(
            release_path=availability_release,
            availability_path=availability_path,
            qa_path=availability_qa,
            raw_root=directory / "raw",
            capture_date="2026-10-17",
        )
        plan_path = directory / "capture_plan.json"
        plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        plan_qa = verify_plan(plan_path, sha256_file(plan_path))
        plan_qa_path = directory / "capture_plan_qa.json"
        plan_qa_path.write_text(json.dumps(plan_qa, indent=2) + "\n", encoding="utf-8")
        return plan_path, plan_qa_path, plan["availability_result"]["created_at"]

    def make_release(self, directory: Path) -> tuple[Path, Path, Path, str]:
        plan_path, plan_qa_path, availability_created_at = self.make_plan(directory)
        availability_time = parse_time(availability_created_at)
        not_before = (availability_time + timedelta(hours=24)).isoformat()
        created_at = (availability_time + timedelta(hours=1)).isoformat()
        report_path = directory / "capture_report.json"
        release = build_release(
            plan_path=plan_path,
            qa_path=plan_qa_path,
            not_before=not_before,
            report_path=report_path,
            created_at=created_at,
        )
        release_path = directory / "capture_release.json"
        release_path.write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
        return release_path, plan_path, report_path, not_before

    def test_exact_24_hour_boundary_passes_and_preserves_archive_only_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            release_path, _, _, not_before = self.make_release(Path(tmp))
            result = verify(release_path)
        self.assertEqual(result["status"], "PASS_ARCHIVE_ONLY_CAPTURE_RELEASE")
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["checks"]["minimum_cooldown_seconds"], 86400)
        self.assertEqual(result["checks"]["not_before"], not_before)
        self.assertEqual(result["checks"]["minimum_delay_seconds"], 30.0)
        self.assertTrue(result["checks"]["archive_host_only"])
        self.assertTrue(result["checks"]["raw_replay_modifier_used"])
        self.assertFalse(result["decision"]["candidate_live_domain_access_allowed"])
        self.assertFalse(result["decision"]["text_extraction_allowed"])

    def test_builder_rejects_cooldown_one_second_short(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            plan_path, plan_qa_path, availability_created_at = self.make_plan(directory)
            availability_time = parse_time(availability_created_at)
            with self.assertRaisesRegex(ValueError, "less than 24 hours"):
                build_release(
                    plan_path=plan_path,
                    qa_path=plan_qa_path,
                    not_before=(availability_time + timedelta(hours=24, seconds=-1)).isoformat(),
                    report_path=directory / "capture_report.json",
                    created_at=(availability_time + timedelta(hours=1)).isoformat(),
                )

    def test_verifier_recomputes_and_rejects_tampered_cooldown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            release_path, _, _, _ = self.make_release(directory)
            release = load_object(release_path)
            availability_time = parse_time(release["inputs"]["final_availability_result"]["created_at"])
            release["execution_contract"]["not_before"] = (
                availability_time + timedelta(hours=23, minutes=59)
            ).isoformat()
            release["cooldown_contract"]["not_before"] = release["execution_contract"]["not_before"]
            release_path.write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
            result = verify(release_path)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("less than 24 hours" in error for error in result["errors"]))

    def test_builder_and_verifier_both_enforce_no_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            plan_path, plan_qa_path, availability_created_at = self.make_plan(directory)
            availability_time = parse_time(availability_created_at)
            report_path = directory / "capture_report.json"
            report_path.write_text("existing", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "already exists"):
                build_release(
                    plan_path=plan_path,
                    qa_path=plan_qa_path,
                    not_before=(availability_time + timedelta(hours=24)).isoformat(),
                    report_path=report_path,
                    created_at=(availability_time + timedelta(hours=1)).isoformat(),
                )

            report_path.unlink()
            release_path, _, report_path, _ = self.make_release(directory)
            report_path.with_suffix(report_path.suffix + ".partial").write_text("partial", encoding="utf-8")
            result = verify(release_path)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("already exists" in error for error in result["errors"]))

    def test_verified_v2_release_remains_compatible_with_frozen_executor_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            release_path, plan_path, _, _ = self.make_release(directory)
            release_qa = verify(release_path)
            release_qa_path = directory / "capture_release_qa.json"
            release_qa_path.write_text(json.dumps(release_qa, indent=2) + "\n", encoding="utf-8")
            validated_release, validated_plan = executor_validate_release(release_path, release_qa_path)
            expected_plan_id = load_object(plan_path)["report_id"]
        self.assertEqual(validated_release["tooling_version"], "v2")
        self.assertEqual(validated_plan["report_id"], expected_plan_id)


if __name__ == "__main__":
    unittest.main()
