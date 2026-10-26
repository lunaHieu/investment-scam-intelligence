import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_sec_edgar_iapd_v11_metadata_recovery_release import EXPECTED_IDS, RELEASE_ID, RELEASE_QA_STATUS
from scripts.verify_sec_edgar_iapd_v11_metadata_recovery_result import verify


class V11MetadataRecoveryResultTests(unittest.TestCase):
    def _fixture(self, metadata: bool = True) -> tuple[Path, Path, Path, tempfile.TemporaryDirectory[str]]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        raw_root = root / "raw"
        raw_root.mkdir()
        rows = []
        for index, identity in enumerate(EXPECTED_IDS):
            raw = raw_root / f"{identity}.html"
            payload = f"<html><body>row {index}</body></html>".encode()
            raw.write_bytes(payload)
            rows.append({
                "availability_plan_id": identity,
                "shortlist_id": f"SHORT_{index}",
                "cohort": "EXTERNAL_HOLDOUT",
                "candidate_host": f"example{index}.invalid",
                "candidate_url": f"https://example{index}.invalid/",
                "snapshot_timestamp": "20240101000000",
                "snapshot_url": f"https://web.archive.org/web/20240101000000id_/https://example{index}.invalid/",
                "requested_archive_url": f"https://web.archive.org/web/20240101000000id_/https://example{index}.invalid/",
                "capture_path": str(raw),
            })
        plan = {"report_id": "ISI_SEC_EDGAR_IAPD_V11_METADATA_RECOVERY_PLAN_V1", "results": rows}
        plan_path = root / "plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        release = {"release_id": RELEASE_ID, "planned_output": {"report_id": "REPORT", "path": str(root / "report.json")}, "inputs": {"recovery_plan": {"path": str(plan_path), "sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest()}}}
        release_path = root / "release.json"
        release_path.write_text(json.dumps(release), encoding="utf-8")
        release_qa = {"status": RELEASE_QA_STATUS, "release": {"sha256": hashlib.sha256(release_path.read_bytes()).hexdigest()}}
        qa_path = root / "release_qa.json"
        qa_path.write_text(json.dumps(release_qa), encoding="utf-8")
        result_rows = []
        for row in rows:
            raw = Path(row["capture_path"])
            item = {**row, "outcome": "CAPTURED", "final_archive_url": row["snapshot_url"], "redirect_count": 0, "http_status": 200, "content_type": "text/html; charset=utf-8", "bytes": raw.stat().st_size, "sha256": hashlib.sha256(raw.read_bytes()).hexdigest(), "attempt_count": 1, "diagnostics": {"Date": "Mon, 01 Jan 2024 00:00:00 GMT"}, "error": None}
            if not metadata:
                item["final_archive_url"] = None
            result_rows.append(item)
        report = {"report_id": "REPORT", "release": {"sha256": hashlib.sha256(release_path.read_bytes()).hexdigest()}, "release_qa": {"sha256": hashlib.sha256(qa_path.read_bytes()).hexdigest()}, "planned_capture_count": 2, "network_request_count": 2, "captured_count": 2, "failed_count": 0, "not_attempted_count": 0, "captured_by_cohort": {"EXTERNAL_HOLDOUT": 2}, "stopped_on_http_429": False, "status": "COMPLETE", "results": result_rows, "safety_contract": {"candidate_live_domain_access_operations": 0, "only_web_archive_host_accessed": True, "raw_replay_modifier_used": True, "automatic_external_redirect_following": False, "labels_created": 0, "model_operations": 0, "training_allowed": False}}
        report_path = root / "report.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        return release_path, qa_path, report_path, temp

    def test_complete_result_requires_persisted_metadata(self) -> None:
        release, qa, report, temp = self._fixture(metadata=True)
        with temp:
            result = verify(release, qa, report)
        self.assertEqual(result["status"], "PASS_COMPLETE_V11_METADATA_RECOVERY_CAPTURE_METADATA_VERIFIED_EXACT_TEXT_RELEASE_MAY_BE_PREPARED")
        self.assertEqual(result["errors"], [])

    def test_missing_final_archive_metadata_fails_closed(self) -> None:
        release, qa, report, temp = self._fixture(metadata=False)
        with temp:
            result = verify(release, qa, report)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("final URL" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
