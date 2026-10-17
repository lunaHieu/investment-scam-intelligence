import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_sec_edgar_iapd_wayback_capture_plan_v3 import build_plan
from scripts.verify_sec_edgar_iapd_wayback_capture_plan_v3 import verify
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


ROOT = Path(__file__).resolve().parents[1]
RELEASES = {
    generation: ROOT / "configs" / f"sec_edgar_iapd_wayback_availability_retry_release_{generation}.json"
    for generation in ("v3", "v4", "v5", "v6")
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


def write_fixture(directory: Path, generation: str = "v6") -> tuple[Path, Path, Path]:
    release_path = RELEASES[generation]
    result_path = directory / f"availability_{generation}.json"
    result_path.write_text(
        json.dumps(make_complete_result(release_path, generation), indent=2) + "\n",
        encoding="utf-8",
    )
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


class SecEdgarIapdWaybackCapturePlanV3Tests(unittest.TestCase):
    def test_complete_v6_builds_and_verifies_all_and_only_available_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            release_path, result_path, qa_path = write_fixture(directory)
            plan = build_plan(
                release_path=release_path,
                availability_path=result_path,
                qa_path=qa_path,
                raw_root=directory / "raw",
                capture_date="2026-10-19",
            )
            plan_path = directory / "capture_plan.json"
            plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
            checked = verify(plan_path, sha256_file(plan_path))
            source = read_jsonl(Path(load_object(release_path)["inputs"]["availability_plan"]["path"]))

        self.assertEqual(plan["tooling_version"], "v3")
        self.assertEqual(plan["availability_generation"], "v6")
        self.assertEqual(plan["planned_capture_count"], 2)
        self.assertEqual(plan["planned_by_cohort"], {"DEVELOPMENT": 1, "EXTERNAL_HOLDOUT": 1})
        self.assertEqual(
            [row["availability_plan_id"] for row in plan["results"]],
            [source[0]["availability_plan_id"], source[-1]["availability_plan_id"]],
        )
        self.assertEqual(checked["status"], "PASS_EXACT_AVAILABLE_SNAPSHOT_PLAN_REGISTER_BEFORE_EXECUTION")
        self.assertEqual(checked["errors"], [])
        self.assertTrue(checked["checks"]["complete_population_recomputed"])
        self.assertFalse(checked["decision"]["archived_page_download_allowed_by_this_qa"])

    def test_partial_v6_disguised_as_complete_fails_recomputation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            release_path, result_path, qa_path = write_fixture(directory)
            result = load_object(result_path)
            result["results"][1]["available"] = None
            result["results"][1]["error"] = "TimeoutError: synthetic"
            # Intentionally retain the claimed COMPLETE/zero-unresolved aggregates.
            result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            qa = load_object(qa_path)
            qa["inputs"]["v6_sha256"] = sha256_file(result_path)
            qa_path.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unresolved rows"):
                build_plan(
                    release_path=release_path,
                    availability_path=result_path,
                    qa_path=qa_path,
                    raw_root=directory / "raw",
                    capture_date="2026-10-19",
                )

    def test_cross_generation_qa_identity_and_hash_binding_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            release_path, result_path, qa_path = write_fixture(directory)
            qa = load_object(qa_path)
            qa["verification_id"] = "ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_RESULT_INDEPENDENT_QA_V5"
            qa["inputs"] = {"v5_sha256": sha256_file(result_path)}
            qa_path.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "QA identity"):
                build_plan(
                    release_path=release_path,
                    availability_path=result_path,
                    qa_path=qa_path,
                    raw_root=directory / "raw",
                    capture_date="2026-10-19",
                )

    def test_v3_tooling_retains_explicit_prior_generation_support(self) -> None:
        for generation in ("v3", "v4", "v5"):
            with self.subTest(generation=generation), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                release_path, result_path, qa_path = write_fixture(directory, generation)
                plan = build_plan(
                    release_path=release_path,
                    availability_path=result_path,
                    qa_path=qa_path,
                    raw_root=directory / "raw",
                    capture_date="2026-10-19",
                )
                self.assertEqual(plan["availability_generation"], generation)


if __name__ == "__main__":
    unittest.main()
