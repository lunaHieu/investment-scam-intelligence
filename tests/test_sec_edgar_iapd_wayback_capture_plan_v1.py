import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_sec_edgar_iapd_wayback_capture_plan_v1 import build_plan
from scripts.verify_sec_edgar_iapd_wayback_capture_plan_v1 import verify
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "sec_edgar_iapd_wayback_availability_retry_release_v3.json"
RELEASE_DATA = load_object(RELEASE)
SOURCE_PLAN = Path(RELEASE_DATA["inputs"]["availability_plan"]["path"])


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def make_complete_result() -> dict:
    results = []
    source = read_jsonl(SOURCE_PLAN)
    available_indexes = {0, len(source) - 1}
    for index, row in enumerate(source):
        available = index in available_indexes
        results.append({
            "availability_plan_id": row["availability_plan_id"],
            "shortlist_id": row["shortlist_id"],
            "cohort": row["cohort"],
            "candidate_host": row["candidate_host"],
            "candidate_url": row["candidate_url"],
            "query_timestamp": row["target_timestamp"],
            "queried": True,
            "available": available,
            "snapshot_timestamp": "20260901010203" if available else None,
            "snapshot_url": f"https://web.archive.org/web/20260901010203/{row['candidate_url']}" if available else None,
            "snapshot_http_status": "200" if available else None,
            "error": None,
        })
    return {
        "report_id": "ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_AVAILABILITY_REPORT_V3",
        "created_at": RELEASE_DATA["cooldown_contract"]["not_before"],
        "status": "COMPLETE",
        "release_sha256": sha256_file(RELEASE),
        "requested_candidate_count": 115,
        "available_snapshot_count": 2,
        "unavailable_snapshot_count": 113,
        "unresolved_error_count": 0,
        "capture_plan_construction_ready": True,
        "results": results,
    }


def write_fixture(directory: Path) -> tuple[Path, Path]:
    result_path = directory / "availability_v3.json"
    result_path.write_text(json.dumps(make_complete_result(), indent=2) + "\n", encoding="utf-8")
    qa = {
        "verification_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_RESULT_INDEPENDENT_QA_V3",
        "status": "PASS_COMPLETE_CAPTURE_PLAN_MAY_BE_PREPARED",
        "inputs": {"v3_sha256": sha256_file(result_path)},
        "checks": {"capture_plan_construction_ready": True},
        "errors": [],
    }
    qa_path = directory / "availability_qa_v3.json"
    qa_path.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
    return result_path, qa_path


class SecEdgarIapdWaybackCapturePlanV1Tests(unittest.TestCase):
    def test_builder_preserves_all_available_rows_and_cohort_separation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            result_path, qa_path = write_fixture(directory)
            plan = build_plan(
                release_path=RELEASE,
                availability_path=result_path,
                qa_path=qa_path,
                raw_root=directory / "raw",
                capture_date="2026-10-14",
            )
        self.assertEqual(plan["planned_capture_count"], 2)
        self.assertEqual(plan["planned_by_cohort"], {"DEVELOPMENT": 1, "EXTERNAL_HOLDOUT": 1})
        self.assertEqual(plan["unavailable_candidates_not_planned"], 113)
        self.assertTrue(all("id_/" in row["requested_archive_url"] for row in plan["results"]))
        self.assertEqual(
            [row["availability_plan_id"] for row in plan["results"]],
            [read_jsonl(SOURCE_PLAN)[0]["availability_plan_id"], read_jsonl(SOURCE_PLAN)[-1]["availability_plan_id"]],
        )

    def test_independent_verifier_passes_exact_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            result_path, qa_path = write_fixture(directory)
            plan = build_plan(
                release_path=RELEASE,
                availability_path=result_path,
                qa_path=qa_path,
                raw_root=directory / "raw",
                capture_date="2026-10-14",
            )
            plan_path = directory / "capture_plan.json"
            plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
            result = verify(plan_path, sha256_file(plan_path))
        self.assertEqual(result["status"], "PASS_EXACT_AVAILABLE_SNAPSHOT_PLAN_REGISTER_BEFORE_EXECUTION")
        self.assertEqual(result["errors"], [])
        self.assertTrue(result["checks"]["all_and_only_available_rows_planned_in_order"])
        self.assertFalse(result["decision"]["archived_page_download_allowed_by_this_qa"])

    def test_builder_rejects_partial_availability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            result_path, qa_path = write_fixture(directory)
            result = load_object(result_path)
            result["status"] = "INCOMPLETE_ERRORS_PRESERVED"
            result["unresolved_error_count"] = 1
            result["capture_plan_construction_ready"] = False
            result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            qa = load_object(qa_path)
            qa["inputs"]["v3_sha256"] = sha256_file(result_path)
            qa_path.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not complete"):
                build_plan(
                    release_path=RELEASE,
                    availability_path=result_path,
                    qa_path=qa_path,
                    raw_root=directory / "raw",
                    capture_date="2026-10-14",
                )


if __name__ == "__main__":
    unittest.main()
