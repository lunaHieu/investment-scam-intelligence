import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_sec_edgar_iapd_wayback_capture_retry_release_v1 import (
    build_retry_release,
)
from scripts.verify_sec_edgar_iapd_wayback_capture_retry_release_v1 import verify
from scripts.verify_sec_edgar_iapd_wayback_capture_result_v1 import (
    verify as verify_capture_result,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def make_row(directory: Path, index: int) -> dict:
    timestamp = f"2026101000000{index}"
    candidate = f"example-{index}.test"
    return {
        "availability_plan_id": f"availability-{index}",
        "shortlist_id": f"shortlist-{index}",
        "cohort": "DEVELOPMENT" if index < 3 else "EXTERNAL_HOLDOUT",
        "candidate_host": candidate,
        "candidate_url": f"https://{candidate}/",
        "snapshot_timestamp": timestamp,
        "snapshot_url": f"https://web.archive.org/web/{timestamp}/https://{candidate}/",
        "requested_archive_url": f"https://web.archive.org/web/{timestamp}id_/https://{candidate}/",
        "capture_path": str((directory / "raw" / f"capture-{index}.html").resolve()),
    }


def write_partial_fixture(directory: Path) -> dict:
    rows = [make_row(directory, index) for index in range(4)]
    payloads = [b"<html>completed-zero</html>", b"<html>completed-one</html>"]
    results = []
    for index, row in enumerate(rows):
        if index < 2:
            target = Path(row["capture_path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payloads[index])
            results.append(
                {
                    **row,
                    "outcome": "CAPTURED",
                    "final_archive_url": row["requested_archive_url"],
                    "redirect_count": 0,
                    "http_status": 200,
                    "content_type": "text/html",
                    "bytes": len(payloads[index]),
                    "sha256": hashlib.sha256(payloads[index]).hexdigest(),
                    "error": None,
                }
            )
        elif index == 2:
            results.append(
                {
                    **row,
                    "outcome": "FAILED",
                    "final_archive_url": None,
                    "redirect_count": None,
                    "http_status": 429,
                    "content_type": None,
                    "bytes": None,
                    "sha256": None,
                    "error": "HTTPError: 429 Too Many Requests",
                }
            )
        else:
            results.append(
                {
                    **row,
                    "outcome": "NOT_ATTEMPTED_AFTER_HTTP_429_STOP",
                    "final_archive_url": None,
                    "redirect_count": None,
                    "http_status": None,
                    "content_type": None,
                    "bytes": None,
                    "sha256": None,
                    "error": "NOT_ATTEMPTED_AFTER_HTTP_429_STOP",
                }
            )

    plan_path = directory / "capture_plan.json"
    write_json(
        plan_path,
        {"report_id": "PLAN", "planned_capture_count": 4, "results": rows},
    )
    source_release_path = directory / "source_release.json"
    plan_binding = {
        "path": str(plan_path.resolve()),
        "sha256": sha256_file(plan_path),
        "record_count": 4,
    }
    write_json(
        source_release_path,
        {
            "release_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_CAPTURE_EXECUTION_RELEASE_V1",
            "inputs": {"capture_plan": plan_binding},
            "planned_output": {"report_id": "SOURCE_CAPTURE_REPORT"},
        },
    )
    source_release_qa_path = directory / "source_release_qa.json"
    write_json(
        source_release_qa_path,
        {
            "status": "PASS_ARCHIVE_ONLY_CAPTURE_RELEASE",
            "release": {"sha256": sha256_file(source_release_path)},
        },
    )
    report_path = directory / "capture_report.json"
    write_json(
        report_path,
        {
            "report_id": "SOURCE_CAPTURE_REPORT",
            "created_at": "2026-10-16T02:00:00+07:00",
            "status": "INCOMPLETE_FAILURES_PRESERVED",
            "release": {"sha256": sha256_file(source_release_path)},
            "release_qa": {"sha256": sha256_file(source_release_qa_path)},
            "plan": plan_binding,
            "planned_capture_count": 4,
            "network_request_count": 3,
            "captured_count": 2,
            "captured_by_cohort": {"DEVELOPMENT": 2},
            "failed_count": 1,
            "not_attempted_count": 1,
            "stopped_on_http_429": True,
            "results": results,
        },
    )
    qa = verify_capture_result(source_release_path, source_release_qa_path, report_path)
    if qa["status"] != "PASS_PARTIAL_CAPTURE_RETRY_REQUIRED_TEXT_EXTRACTION_BLOCKED":
        raise AssertionError(qa)
    qa_path = directory / "independent_partial_qa.json"
    write_json(qa_path, qa)
    return {
        "qa_path": qa_path,
        "source_release_path": source_release_path,
        "source_release_qa_path": source_release_qa_path,
        "report_path": report_path,
        "results": results,
    }


class SecEdgarIapdWaybackCaptureRetryReleaseV1Tests(unittest.TestCase):
    def build(self, directory: Path) -> tuple[dict, dict]:
        fixture = write_partial_fixture(directory)
        retry_report = directory / "capture_retry_report.json"
        release = build_retry_release(
            partial_qa_path=fixture["qa_path"],
            source_release_path=fixture["source_release_path"],
            source_release_qa_path=fixture["source_release_qa_path"],
            capture_report_path=fixture["report_path"],
            not_before="2026-10-17T02:00:00+07:00",
            report_path=retry_report,
            created_at="2026-10-16T03:00:00+07:00",
        )
        return release, fixture

    def test_selects_exact_missing_rows_and_preserves_completed_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            release, fixture = self.build(directory)
            results = fixture["results"]
            qa = json.loads(fixture["qa_path"].read_text(encoding="utf-8"))
            self.assertEqual(
                qa["verification_id"],
                "ISI_SEC_EDGAR_IAPD_WAYBACK_CAPTURE_RESULT_INDEPENDENT_QA_V1",
            )
            self.assertNotIn("artifacts", qa)
            self.assertEqual(
                set(qa["inputs"]),
                {
                    "release_sha256",
                    "release_qa_sha256",
                    "report_sha256",
                    "plan_sha256",
                },
            )
            self.assertEqual(release["source_population_count"], 4)
            self.assertEqual(release["completed_capture_count"], 2)
            self.assertEqual(release["retry_capture_count"], 2)
            self.assertEqual(
                [row["shortlist_id"] for row in release["retry_rows"]],
                [results[2]["shortlist_id"], results[3]["shortlist_id"]],
            )
            self.assertEqual(
                [row["sha256"] for row in release["completed_capture_ledger"]],
                [results[0]["sha256"], results[1]["sha256"]],
            )
            self.assertEqual(release["execution_contract"]["maximum_attempts_per_snapshot"], 1)
            self.assertTrue(release["execution_contract"]["stop_on_http_429"])
            self.assertEqual(release["execution_contract"]["allowed_network_hosts"], ["web.archive.org"])

    def test_independent_verifier_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            release, _ = self.build(directory)
            release_path = directory / "retry_release.json"
            write_json(release_path, release)
            result = verify(release_path)
            self.assertEqual(result["status"], "PASS_EXACT_MISSING_ROWS_ARCHIVE_ONLY_RETRY_RELEASE")
            self.assertEqual(result["checks"]["retry_capture_count"], 2)
            self.assertTrue(result["checks"]["completed_bytes_and_hashes_preserved"])
            self.assertFalse(result["decision"]["text_extraction_allowed"])

    def test_rejects_cooldown_shorter_than_24_hours(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            fixture = write_partial_fixture(directory)
            with self.assertRaisesRegex(ValueError, "less than 24 hours"):
                build_retry_release(
                    partial_qa_path=fixture["qa_path"],
                    source_release_path=fixture["source_release_path"],
                    source_release_qa_path=fixture["source_release_qa_path"],
                    capture_report_path=fixture["report_path"],
                    not_before="2026-10-17T01:59:59+07:00",
                    report_path=directory / "retry_report.json",
                    created_at="2026-10-16T03:00:00+07:00",
                )

    def test_rejects_completed_byte_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            fixture = write_partial_fixture(directory)
            results = fixture["results"]
            Path(results[0]["capture_path"]).write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "byte/hash mismatch"):
                build_retry_release(
                    partial_qa_path=fixture["qa_path"],
                    source_release_path=fixture["source_release_path"],
                    source_release_qa_path=fixture["source_release_qa_path"],
                    capture_report_path=fixture["report_path"],
                    not_before="2026-10-17T02:00:00+07:00",
                    report_path=directory / "retry_report.json",
                    created_at="2026-10-16T03:00:00+07:00",
                )

    def test_rejects_explicit_source_that_does_not_match_qa_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            fixture = write_partial_fixture(directory)
            report = json.loads(fixture["report_path"].read_text(encoding="utf-8"))
            report["network_request_count"] = 4
            write_json(fixture["report_path"], report)
            with self.assertRaisesRegex(ValueError, "input hashes do not match explicit sources"):
                build_retry_release(
                    partial_qa_path=fixture["qa_path"],
                    source_release_path=fixture["source_release_path"],
                    source_release_qa_path=fixture["source_release_qa_path"],
                    capture_report_path=fixture["report_path"],
                    not_before="2026-10-17T02:00:00+07:00",
                    report_path=directory / "retry_report.json",
                    created_at="2026-10-16T03:00:00+07:00",
                )

    def test_rejects_nonexact_partial_qa_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            fixture = write_partial_fixture(directory)
            qa = json.loads(fixture["qa_path"].read_text(encoding="utf-8"))
            qa["decision"]["training_allowed"] = True
            write_json(fixture["qa_path"], qa)
            with self.assertRaisesRegex(ValueError, "decisions do not match"):
                build_retry_release(
                    partial_qa_path=fixture["qa_path"],
                    source_release_path=fixture["source_release_path"],
                    source_release_qa_path=fixture["source_release_qa_path"],
                    capture_report_path=fixture["report_path"],
                    not_before="2026-10-17T02:00:00+07:00",
                    report_path=directory / "retry_report.json",
                    created_at="2026-10-16T03:00:00+07:00",
                )

    def test_verifier_rejects_changed_retry_population(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            release, _ = self.build(directory)
            release["retry_rows"].reverse()
            release_path = directory / "retry_release.json"
            write_json(release_path, release)
            result = verify(release_path)
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("Retry population/order changed", result["errors"])


if __name__ == "__main__":
    unittest.main()
