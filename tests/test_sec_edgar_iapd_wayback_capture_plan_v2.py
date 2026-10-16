import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_sec_edgar_iapd_wayback_capture_plan_v2 import build_plan
from scripts.build_sec_edgar_iapd_wayback_capture_release_v1 import build_release
from scripts.verify_sec_edgar_iapd_wayback_capture_plan_v2 import verify
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


ROOT = Path(__file__).resolve().parents[1]
RELEASES = {
    generation: ROOT / "configs" / f"sec_edgar_iapd_wayback_availability_retry_release_{generation}.json"
    for generation in ("v3", "v4", "v5")
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def make_complete_result(release_path: Path, generation: str) -> dict:
    release = load_object(release_path)
    source = read_jsonl(Path(release["inputs"]["availability_plan"]["path"]))
    available_indexes = {0, len(source) - 1}
    results = []
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
        "report_id": f"ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_AVAILABILITY_REPORT_{generation.upper()}",
        "created_at": release["cooldown_contract"]["not_before"],
        "status": "COMPLETE",
        "release_sha256": sha256_file(release_path),
        "requested_candidate_count": 115,
        "available_snapshot_count": 2,
        "unavailable_snapshot_count": 113,
        "unresolved_error_count": 0,
        "capture_plan_construction_ready": True,
        "results": results,
    }


def write_fixture(directory: Path, generation: str) -> tuple[Path, Path, Path]:
    release_path = RELEASES[generation]
    result_path = directory / f"availability_{generation}.json"
    result_path.write_text(json.dumps(make_complete_result(release_path, generation), indent=2) + "\n", encoding="utf-8")
    qa = {
        "verification_id": f"ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_RESULT_INDEPENDENT_QA_{generation.upper()}",
        "status": "PASS_COMPLETE_CAPTURE_PLAN_MAY_BE_PREPARED",
        "inputs": {f"{generation}_sha256": sha256_file(result_path)},
        "checks": {"capture_plan_construction_ready": True},
        "errors": [],
    }
    qa_path = directory / f"availability_qa_{generation}.json"
    qa_path.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
    return release_path, result_path, qa_path


class SecEdgarIapdWaybackCapturePlanV2Tests(unittest.TestCase):
    def test_all_supported_complete_generations_build_and_verify_exact_plan(self) -> None:
        for generation in ("v3", "v4", "v5"):
            with self.subTest(generation=generation), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                release_path, result_path, qa_path = write_fixture(directory, generation)
                plan = build_plan(
                    release_path=release_path,
                    availability_path=result_path,
                    qa_path=qa_path,
                    raw_root=directory / "raw",
                    capture_date="2026-10-17",
                )
                plan_path = directory / "capture_plan.json"
                plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
                checked = verify(plan_path, sha256_file(plan_path))
                source_plan = Path(load_object(release_path)["inputs"]["availability_plan"]["path"])
                source_rows = read_jsonl(source_plan)

                self.assertEqual(plan["availability_generation"], generation)
                self.assertEqual(plan["planned_capture_count"], 2)
                self.assertEqual(plan["planned_by_cohort"], {"DEVELOPMENT": 1, "EXTERNAL_HOLDOUT": 1})
                self.assertEqual(plan["unavailable_candidates_not_planned"], 113)
                self.assertEqual(
                    [row["availability_plan_id"] for row in plan["results"]],
                    [source_rows[0]["availability_plan_id"], source_rows[-1]["availability_plan_id"]],
                )
                self.assertEqual(checked["status"], "PASS_EXACT_AVAILABLE_SNAPSHOT_PLAN_REGISTER_BEFORE_EXECUTION")
                self.assertEqual(checked["errors"], [])
                self.assertEqual(checked["checks"]["availability_generation"], generation)
                self.assertFalse(checked["decision"]["archived_page_download_allowed_by_this_qa"])

    def test_v5_partial_result_remains_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            release_path, result_path, qa_path = write_fixture(directory, "v5")
            result = load_object(result_path)
            result["status"] = "INCOMPLETE_ERRORS_PRESERVED"
            result["unresolved_error_count"] = 1
            result["capture_plan_construction_ready"] = False
            result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            qa = load_object(qa_path)
            qa["inputs"]["v5_sha256"] = sha256_file(result_path)
            qa_path.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not complete"):
                build_plan(
                    release_path=release_path,
                    availability_path=result_path,
                    qa_path=qa_path,
                    raw_root=directory / "raw",
                    capture_date="2026-10-17",
                )

    def test_v5_plan_and_v2_qa_remain_compatible_with_frozen_capture_release_v1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            availability_release, result_path, availability_qa = write_fixture(directory, "v5")
            plan = build_plan(
                release_path=availability_release,
                availability_path=result_path,
                qa_path=availability_qa,
                raw_root=directory / "raw",
                capture_date="2026-10-17",
            )
            plan_path = directory / "capture_plan.json"
            plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
            plan_sha256 = sha256_file(plan_path)
            plan_qa = verify(plan_path, plan_sha256)
            plan_qa_path = directory / "capture_plan_qa.json"
            plan_qa_path.write_text(json.dumps(plan_qa, indent=2) + "\n", encoding="utf-8")
            capture_release = build_release(
                plan_path=plan_path,
                qa_path=plan_qa_path,
                not_before="2026-10-18T02:00:00+07:00",
                report_path=directory / "capture_report.json",
                created_at="2026-10-17T02:00:00+07:00",
            )

        self.assertEqual(capture_release["inputs"]["capture_plan"]["sha256"], plan_sha256)
        self.assertEqual(capture_release["execution_contract"]["minimum_delay_seconds"], 30.0)
        self.assertFalse(capture_release["decision"]["candidate_live_domain_access_allowed"])

    def test_v5_qa_cannot_bind_through_an_older_generation_hash_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            release_path, result_path, qa_path = write_fixture(directory, "v5")
            qa = load_object(qa_path)
            qa["inputs"] = {"v4_sha256": sha256_file(result_path)}
            qa_path.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "result generation"):
                build_plan(
                    release_path=release_path,
                    availability_path=result_path,
                    qa_path=qa_path,
                    raw_root=directory / "raw",
                    capture_date="2026-10-17",
                )

    def test_result_must_be_bound_to_the_supplied_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            release_path, result_path, qa_path = write_fixture(directory, "v5")
            result = load_object(result_path)
            result["release_sha256"] = "0" * 64
            result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            qa = load_object(qa_path)
            qa["inputs"]["v5_sha256"] = sha256_file(result_path)
            qa_path.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "supplied release"):
                build_plan(
                    release_path=release_path,
                    availability_path=result_path,
                    qa_path=qa_path,
                    raw_root=directory / "raw",
                    capture_date="2026-10-17",
                )

    def test_release_identity_must_match_result_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            release = load_object(RELEASES["v5"])
            release["release_id"] = "ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_RETRY_RELEASE_V4"
            release_path = directory / "wrong_generation_release.json"
            release_path.write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
            result_path = directory / "availability_v5.json"
            result_path.write_text(json.dumps(make_complete_result(release_path, "v5"), indent=2) + "\n", encoding="utf-8")
            qa_path = directory / "availability_qa_v5.json"
            qa_path.write_text(json.dumps({
                "status": "PASS_COMPLETE_CAPTURE_PLAN_MAY_BE_PREPARED",
                "inputs": {"v5_sha256": sha256_file(result_path)},
                "checks": {"capture_plan_construction_ready": True},
            }, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "release identity"):
                build_plan(
                    release_path=release_path,
                    availability_path=result_path,
                    qa_path=qa_path,
                    raw_root=directory / "raw",
                    capture_date="2026-10-17",
                )

    def test_verifier_rejects_closed_availability_capture_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            release_path, result_path, qa_path = write_fixture(directory, "v5")
            plan = build_plan(
                release_path=release_path,
                availability_path=result_path,
                qa_path=qa_path,
                raw_root=directory / "raw",
                capture_date="2026-10-17",
            )
            result = load_object(result_path)
            result["capture_plan_construction_ready"] = False
            result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            result_hash = sha256_file(result_path)
            qa = load_object(qa_path)
            qa["inputs"]["v5_sha256"] = result_hash
            qa_path.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
            plan["availability_result"]["sha256"] = result_hash
            plan["independent_availability_qa"]["sha256"] = sha256_file(qa_path)
            plan_path = directory / "capture_plan.json"
            plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")

            checked = verify(plan_path, sha256_file(plan_path))

        self.assertEqual(checked["status"], "FAIL")
        self.assertIn(
            "Availability result kept capture-plan construction closed",
            checked["errors"],
        )


if __name__ == "__main__":
    unittest.main()
