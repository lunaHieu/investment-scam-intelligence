import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from scripts.execute_sec_edgar_iapd_v11_metadata_recovery_v2 import USER_AGENT, execute


class V11MetadataRecoveryExecutionV2Tests(unittest.TestCase):
    def _fixture(self, root: Path):
        now = datetime.now(timezone.utc)
        report = root / "report.json"
        release_path = root / "release.json"
        qa_path = root / "qa.json"
        qa_path.write_text("{}", encoding="utf-8")
        release = {
            "execution_contract": {"not_before": (now - timedelta(seconds=1)).isoformat(), "timeout_seconds": 1, "minimum_delay_seconds": 0, "maximum_redirects": 0},
            "planned_output": {"path": str(report), "report_id": "REPORT"},
            "inputs": {"recovery_plan": {"path": str(root / "plan.json"), "sha256": "plan"}},
        }
        release_path.write_text(json.dumps(release), encoding="utf-8")
        row = {key: value for key, value in {
            "availability_plan_id": "ID", "shortlist_id": "S", "cohort": "EXTERNAL_HOLDOUT",
            "candidate_host": "example.test", "candidate_url": "https://example.test/",
            "snapshot_timestamp": "20260101000000", "snapshot_url": "https://web.archive.org/web/20260101000000/https://example.test/",
            "requested_archive_url": "https://web.archive.org/web/20260101000000id_/https://example.test/",
            "capture_path": str(root / "raw.html"),
        }.items()}
        return now, report, release_path, qa_path, release, {"results": [row]}

    def test_success_has_final_report_and_no_stale_partial(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            now, report, release_path, qa_path, release, plan = self._fixture(Path(temp))
            with patch("scripts.execute_sec_edgar_iapd_v11_metadata_recovery_v2.validate", return_value=(release, plan)), patch("scripts.execute_sec_edgar_iapd_v11_metadata_recovery_v2.fetch_archive", return_value=(b"<html>ok</html>", "https://web.archive.org/web/20260101000000id_/https://example.test/", 0, "text/html", {"Content-Type": "text/html"})):
                result = execute(release_path, qa_path, now=now)
            self.assertEqual(result["status"], "COMPLETE")
            self.assertTrue(report.is_file())
            self.assertFalse(report.with_suffix(".json.partial").exists())

    def test_network_failure_is_finalized_not_left_as_reservation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            now, report, release_path, qa_path, release, plan = self._fixture(Path(temp))
            with patch("scripts.execute_sec_edgar_iapd_v11_metadata_recovery_v2.validate", return_value=(release, plan)), patch("scripts.execute_sec_edgar_iapd_v11_metadata_recovery_v2.fetch_archive", side_effect=TimeoutError("fixture")):
                result = execute(release_path, qa_path, now=now)
            self.assertEqual(result["status"], "INCOMPLETE_FAILURES_PRESERVED")
            self.assertTrue(report.is_file())
            self.assertFalse(report.with_suffix(".json.partial").exists())

    def test_user_agent_is_versioned_and_identifying(self) -> None:
        self.assertIn("/2.0", USER_AGENT)
        self.assertIn("gpt-5", USER_AGENT)


if __name__ == "__main__":
    unittest.main()
