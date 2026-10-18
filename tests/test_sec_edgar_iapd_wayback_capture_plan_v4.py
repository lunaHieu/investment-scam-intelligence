import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_sec_edgar_iapd_wayback_capture_plan_v4 import build_plan
from scripts.verify_sec_edgar_iapd_wayback_capture_plan_v4 import verify
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


def write_v7_fixture(directory: Path) -> tuple[Path, Path, Path]:
    source_path = directory / "availability_plan.jsonl"
    source = []
    for index in range(115):
        source.append({
            "availability_plan_id": f"AP-{index:03d}",
            "shortlist_id": f"SL-{index:03d}",
            "cohort": "DEVELOPMENT" if index < 90 else "EXTERNAL_HOLDOUT",
            "candidate_host": f"example{index}.test",
            "candidate_url": f"https://example{index}.test/",
            "target_timestamp": "20261003",
        })
    source_path.write_text(
        "".join(json.dumps(row) + "\n" for row in source), encoding="utf-8",
    )
    release = {
        "release_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_RETRY_RELEASE_V7",
        "inputs": {"availability_plan": {
            "path": str(source_path), "sha256": sha256_file(source_path), "record_count": 115,
        }},
        "planned_output": {
            "report_id": "ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_AVAILABILITY_REPORT_V7",
        },
    }
    release_path = directory / "availability_release_v7.json"
    release_path.write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
    available_indexes = {0, 114}
    rows = []
    for index, row in enumerate(source):
        available = index in available_indexes
        rows.append({
            **{key: row[key] for key in (
                "availability_plan_id", "shortlist_id", "cohort", "candidate_host", "candidate_url",
            )},
            "query_timestamp": row["target_timestamp"],
            "queried": True,
            "available": available,
            "snapshot_timestamp": "20261001000000" if available else None,
            "snapshot_url": (
                f"https://web.archive.org/web/20261001000000/{row['candidate_url']}"
                if available else None
            ),
            "snapshot_http_status": "200" if available else None,
            "error": None,
        })
    result = {
        "report_id": "ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_AVAILABILITY_REPORT_V7",
        "created_at": "2026-10-20T10:00:00+07:00",
        "status": "COMPLETE",
        "release_sha256": sha256_file(release_path),
        "requested_candidate_count": 115,
        "available_snapshot_count": 2,
        "unavailable_snapshot_count": 113,
        "unresolved_error_count": 0,
        "capture_plan_construction_ready": True,
        "results": rows,
    }
    result_path = directory / "availability_report_v7.json"
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    qa = {
        "verification_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_RESULT_INDEPENDENT_QA_V7",
        "status": "PASS_COMPLETE_CAPTURE_PLAN_MAY_BE_PREPARED",
        "inputs": {"v7_sha256": sha256_file(result_path)},
        "checks": {"capture_plan_construction_ready": True},
        "errors": [],
    }
    qa_path = directory / "independent_qa_v7.json"
    qa_path.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
    return release_path, result_path, qa_path


class SecEdgarIapdWaybackCapturePlanV4Tests(unittest.TestCase):
    def test_complete_v7_recomputes_115_and_preserves_exact_available_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            release_path, result_path, qa_path = write_v7_fixture(directory)
            plan = build_plan(
                release_path=release_path, availability_path=result_path,
                qa_path=qa_path, raw_root=directory / "raw",
                capture_date="2026-10-20",
            )
            plan_path = directory / "capture_plan_v4.json"
            plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
            checked = verify(plan_path, sha256_file(plan_path))

        self.assertEqual(plan["tooling_version"], "v4")
        self.assertEqual(plan["availability_generation"], "v7")
        self.assertEqual(plan["source_candidate_count"], 115)
        self.assertEqual(plan["planned_capture_count"], 2)
        self.assertEqual(plan["planned_by_cohort"], {"DEVELOPMENT": 1, "EXTERNAL_HOLDOUT": 1})
        self.assertEqual([row["availability_plan_id"] for row in plan["results"]], ["AP-000", "AP-114"])
        self.assertEqual(checked["status"], "PASS_EXACT_AVAILABLE_SNAPSHOT_PLAN_REGISTER_BEFORE_EXECUTION")
        self.assertTrue(checked["checks"]["complete_115_row_population_recomputed"])
        self.assertTrue(checked["checks"]["all_and_only_available_rows_planned_in_order"])

    def test_partial_v7_fails_closed_even_if_claimed_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            release_path, result_path, qa_path = write_v7_fixture(directory)
            result = json.loads(result_path.read_text(encoding="utf-8"))
            result["results"][10]["available"] = None
            result["results"][10]["error"] = "HTTPError: 429 synthetic"
            result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            qa = json.loads(qa_path.read_text(encoding="utf-8"))
            qa["inputs"]["v7_sha256"] = sha256_file(result_path)
            qa_path.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unresolved rows"):
                build_plan(
                    release_path=release_path, availability_path=result_path,
                    qa_path=qa_path, raw_root=directory / "raw",
                    capture_date="2026-10-20",
                )

    def test_nonpassing_or_cross_generation_qa_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            release_path, result_path, qa_path = write_v7_fixture(directory)
            qa = json.loads(qa_path.read_text(encoding="utf-8"))
            qa["status"] = "PASS_PARTIAL_ERRORS_PRESERVED_CAPTURE_PLAN_BLOCKED"
            qa["inputs"]["v6_sha256"] = qa["inputs"]["v7_sha256"]
            qa_path.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "did not pass"):
                build_plan(
                    release_path=release_path, availability_path=result_path,
                    qa_path=qa_path, raw_root=directory / "raw",
                    capture_date="2026-10-20",
                )


if __name__ == "__main__":
    unittest.main()
