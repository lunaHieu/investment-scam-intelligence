import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.build_sec_edgar_iapd_v11_supplemental_capture_plan import (
    AVAILABILITY_QA_ID,
    AVAILABILITY_REPORT_ID,
    EXPECTED_IDS,
    build_plan,
)
from scripts.build_sec_edgar_iapd_v11_supplemental_capture_release import build_release
from scripts.verify_sec_edgar_iapd_v11_supplemental_capture_plan import verify as verify_plan
from scripts.verify_sec_edgar_iapd_v11_supplemental_capture_release import verify as verify_release
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


class SecEdgarIapdV11SupplementalCaptureTests(unittest.TestCase):
    def _fixture(self, directory: Path) -> tuple[Path, Path, Path]:
        source_path = directory / "availability_plan.jsonl"
        source_rows = []
        expected = set(EXPECTED_IDS)
        for index in range(115):
            plan_id = EXPECTED_IDS[0] if index == 10 else EXPECTED_IDS[1] if index == 90 else f"AP-{index:03d}"
            source_rows.append({
                "acquisition_wave_id": "WAVE",
                "archived_page_downloaded": False,
                "artifact_captured": False,
                "availability_endpoint": "https://archive.org/wayback/available",
                "availability_plan_id": plan_id,
                "candidate_host": f"example{index}.test",
                "candidate_live_domain_accessed": False,
                "candidate_url": f"https://example{index}.test/",
                "channel_id": "LEGITIMATE_SEC_EDGAR_LINKED_WAYBACK_WEBSITE",
                "cik": f"{index:010d}",
                "cohort": "EXTERNAL_HOLDOUT" if plan_id in expected else "DEVELOPMENT",
                "ground_truth_status": "UNCERTAIN",
                "iapd_source_record_id": str(index),
                "identity_review_status": "OFFLINE_EXACT_CORE_NAME_EVIDENCE_PASS",
                "label_created": False,
                "plan_status": "PLANNED_NOT_EXECUTED",
                "planned_request_url": f"https://archive.org/wayback/available?url=https%3A%2F%2Fexample{index}.test%2F",
                "shortlist_id": f"SL-{index:03d}",
                "target_timestamp": "20261003",
                "training_eligible": "NO",
                "wayback_queried": False,
            })
        source_path.write_text("".join(json.dumps(row) + "\n" for row in source_rows), encoding="utf-8")

        result_rows = []
        for row in source_rows:
            available = row["availability_plan_id"] in expected
            result_rows.append({
                **{field: row[field] for field in ("availability_plan_id", "shortlist_id", "cohort", "candidate_host", "candidate_url")},
                "query_timestamp": row["target_timestamp"],
                "queried": True,
                "available": available,
                "snapshot_timestamp": "20261001000000" if available else None,
                "snapshot_url": f"https://web.archive.org/web/20261001000000/{row['candidate_url']}" if available else None,
                "snapshot_http_status": "200" if available else None,
                "response_diagnostics": {},
                "error": None,
            })
        availability_path = directory / "availability_report_v11.json"
        availability_path.write_text(json.dumps({
            "report_id": AVAILABILITY_REPORT_ID,
            "created_at": "2026-10-25T05:39:42.463320+07:00",
            "status": "COMPLETE",
            "requested_candidate_count": 115,
            "available_snapshot_count": 2,
            "unavailable_snapshot_count": 113,
            "unresolved_error_count": 0,
            "results": result_rows,
        }, indent=2) + "\n", encoding="utf-8")
        availability_qa_path = directory / "independent_qa_v11.json"
        availability_qa_path.write_text(json.dumps({
            "verification_id": AVAILABILITY_QA_ID,
            "status": "PASS_COMPLETE_SUPPLEMENTAL_AVAILABILITY_RESULT_CAPTURE_PLAN_UNCHANGED",
            "inputs": {"report_sha256": sha256_file(availability_path)},
            "checks": {"resolved_results": 115, "retried_only_exact_two_rows": True},
        }, indent=2) + "\n", encoding="utf-8")
        return source_path, availability_path, availability_qa_path

    def test_build_and_verify_exact_two_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            source, availability, availability_qa = self._fixture(directory)
            plan = build_plan(
                source_plan_path=source, availability_path=availability,
                availability_qa_path=availability_qa, raw_root=directory / "raw",
                capture_date="2026-10-25",
            )
            plan_path = directory / "capture_plan_v1.json"
            plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
            checked = verify_plan(plan_path, sha256_file(plan_path))
            self.assertEqual(checked["status"], "PASS_EXACT_TWO_ROW_SUPPLEMENTAL_CAPTURE_PLAN")
            self.assertEqual([row["availability_plan_id"] for row in plan["results"]], list(EXPECTED_IDS))
            self.assertEqual(plan["planned_by_cohort"], {"EXTERNAL_HOLDOUT": 2})

    def test_release_requires_24_hour_cooldown_and_is_independently_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            source, availability, availability_qa = self._fixture(directory)
            plan = build_plan(
                source_plan_path=source, availability_path=availability,
                availability_qa_path=availability_qa, raw_root=directory / "raw",
                capture_date="2026-10-25",
            )
            plan_path = directory / "capture_plan_v1.json"
            plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
            plan_qa_path = directory / "plan_qa.json"
            plan_qa = verify_plan(plan_path, sha256_file(plan_path))
            plan_qa_path.write_text(json.dumps(plan_qa, indent=2) + "\n", encoding="utf-8")
            created = "2026-10-25T06:00:00+07:00"
            not_before = (datetime.fromisoformat("2026-10-25T05:39:42.463320+07:00") + timedelta(hours=24)).isoformat()
            report = directory / "capture" / "capture_report_v1.json"
            release_path = directory / "release.json"
            release = build_release(
                plan_path=plan_path, plan_qa_path=plan_qa_path,
                availability_path=availability, availability_qa_path=availability_qa,
                not_before=not_before, report_path=report, created_at=created,
            )
            release_path.write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
            checked = verify_release(release_path)
            self.assertEqual(checked["status"], "PASS_ARCHIVE_ONLY_V11_SUPPLEMENTAL_CAPTURE_RELEASE")
            self.assertEqual(release["execution_contract"]["maximum_attempts_per_snapshot"], 1)
            self.assertFalse(release["decision"]["text_extraction_allowed"])

    def test_plan_rejects_unexpected_supplemental_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            source, availability, availability_qa = self._fixture(directory)
            result = json.loads(availability.read_text(encoding="utf-8"))
            result["results"][10]["availability_plan_id"] = "OTHER"
            availability.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "identity mismatch|exact V11 supplemental row"):
                build_plan(
                    source_plan_path=source, availability_path=availability,
                    availability_qa_path=availability_qa, raw_root=directory / "raw",
                    capture_date="2026-10-25",
                )


if __name__ == "__main__":
    unittest.main()
