import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from scripts.build_sec_edgar_iapd_wayback_capture_plan_v3 import build_plan
from scripts.build_sec_edgar_iapd_wayback_capture_release_v3 import build_release, parse_time
from scripts.execute_sec_edgar_iapd_wayback_capture_v1 import validate_release as executor_validate_release
from scripts.verify_sec_edgar_iapd_wayback_capture_plan_v3 import verify as verify_plan
from scripts.verify_sec_edgar_iapd_wayback_capture_release_v3 import verify
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file
from tests.test_sec_edgar_iapd_wayback_capture_plan_v3 import write_fixture


class SecEdgarIapdWaybackCaptureReleaseV3Tests(unittest.TestCase):
    def make_plan(self, directory: Path) -> tuple[Path, Path, str]:
        availability_release, availability_path, availability_qa = write_fixture(directory, "v6")
        plan = build_plan(
            release_path=availability_release,
            availability_path=availability_path,
            qa_path=availability_qa,
            raw_root=directory / "raw",
            capture_date="2026-10-19",
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
        not_before = (availability_time + timedelta(seconds=86400)).isoformat()
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

    def test_exact_cooldown_boundary_passes_with_frozen_archive_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            release_path, _, _, not_before = self.make_release(Path(tmp))
            result = verify(release_path)

        self.assertEqual(result["status"], "PASS_ARCHIVE_ONLY_CAPTURE_RELEASE")
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["checks"]["availability_generation"], "v6")
        self.assertEqual(result["checks"]["minimum_cooldown_seconds"], 86400)
        self.assertEqual(result["checks"]["not_before"], not_before)
        self.assertEqual(result["checks"]["minimum_delay_seconds"], 30.0)
        self.assertEqual(result["checks"]["maximum_attempts_per_snapshot"], 1)
        self.assertTrue(result["checks"]["stop_on_http_429"])
        self.assertFalse(result["checks"]["output_overwrite_allowed"])
        self.assertTrue(result["checks"]["archive_host_only"])

    def test_builder_rejects_cooldown_one_second_short(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            plan_path, plan_qa_path, availability_created_at = self.make_plan(directory)
            availability_time = parse_time(availability_created_at)
            with self.assertRaisesRegex(ValueError, "less than 24 hours"):
                build_release(
                    plan_path=plan_path,
                    qa_path=plan_qa_path,
                    not_before=(availability_time + timedelta(seconds=86399)).isoformat(),
                    report_path=directory / "capture_report.json",
                    created_at=(availability_time + timedelta(hours=1)).isoformat(),
                )

    def test_verifier_rejects_tampered_cooldown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            release_path, _, _, _ = self.make_release(directory)
            release = load_object(release_path)
            availability_time = parse_time(release["inputs"]["final_availability_result"]["created_at"])
            too_early = (availability_time + timedelta(seconds=86399)).isoformat()
            release["execution_contract"]["not_before"] = too_early
            release["cooldown_contract"]["not_before"] = too_early
            release_path.write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
            result = verify(release_path)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("less than 24 hours" in error for error in result["errors"]))

    def test_v3_release_stays_compatible_with_frozen_executor_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            release_path, plan_path, _, _ = self.make_release(directory)
            release_qa = verify(release_path)
            release_qa_path = directory / "capture_release_qa.json"
            release_qa_path.write_text(json.dumps(release_qa, indent=2) + "\n", encoding="utf-8")
            validated_release, validated_plan = executor_validate_release(release_path, release_qa_path)
            expected_plan_id = load_object(plan_path)["report_id"]
        self.assertEqual(validated_release["tooling_version"], "v3")
        self.assertEqual(validated_plan["report_id"], expected_plan_id)


if __name__ == "__main__":
    unittest.main()
