import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.verify_sec_edgar_iapd_wayback_availability_release_v11 import (
    PASS_STATUS,
    verify,
)


MODULE = "scripts.verify_sec_edgar_iapd_wayback_availability_release_v11"
IDS = ["TTCV1_EDGAR_AVAIL_HOLDOUT_011", "TTCV1_EDGAR_AVAIL_HOLDOUT_018"]


class AvailabilityReleaseV11VerifierTests(unittest.TestCase):
    def _run(self, not_before: str):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release_path = root / "configs" / "release.json"
            protocol_path = root / "configs" / "protocol.json"
            qa_path = root / "protocol-qa.json"
            latest_path = root / "latest.json"
            for path in (release_path, protocol_path, qa_path, latest_path):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}", encoding="utf-8")
            retry_rows = [{"availability_plan_id": identifier} for identifier in IDS]
            contract = {"endpoint": "https://archive.org/wayback/available"}
            output = root / "availability_report_v11.json"
            protocol = {
                "ordered_retry_rows": retry_rows,
                "network_contract": contract,
                "future_release_contract": {
                    "absolute_not_before_floor": "2026-10-23T23:35:43.595958+07:00",
                    "planned_output_path": str(output),
                },
            }
            latest = {
                "created_at": "2026-10-24T00:00:00+07:00",
                "network_request_count": 1,
            }
            protocol_qa = {
                "status": "PASS_FROZEN_EXACT_TWO_HOLDOUT_ROWS_TOOLING_READY_RELEASE_REQUIRED",
                "protocol": {"sha256": "h" * 64},
                "errors": [],
            }
            release = {
                "release_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_RELEASE_V11",
                "status": "FROZEN_EXACT_TWO_HOLDOUT_ROWS_NOT_BEFORE_GATE",
                "created_at": "2026-10-24T00:01:00+07:00",
                "basis": [],
                "inputs": {
                    "protocol": {"path": "configs/protocol.json", "sha256": "h" * 64},
                    "protocol_qa": {"path": str(qa_path), "sha256": "h" * 64, "absolute": True},
                    "latest_actual_archive_request_report": {
                        "path": str(latest_path), "sha256": "h" * 64, "absolute": True
                    },
                },
                "ordered_retry_rows": retry_rows,
                "cooldown_contract": {
                    "latest_actual_archive_request_created_at": "2026-10-24T00:00:00+07:00",
                    "minimum_cooldown_seconds": 86400,
                    "not_before": not_before,
                },
                "network_contract": contract,
                "planned_output": {
                    "path": str(output),
                    "report_id": "ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_AVAILABILITY_REPORT_V11",
                },
                "decision": {
                    "exact_two_row_availability_execution_allowed_after_not_before": True,
                    "candidate_live_domain_access_allowed": False,
                    "archived_page_download_allowed": False,
                    "capture_plan_mutation_allowed": False,
                    "labeling_allowed": False,
                    "validation_or_test_opening_allowed": False,
                    "model_scoring_allowed": False,
                    "training_allowed": False,
                },
            }

            def loader(path):
                name = Path(path).name
                return {
                    "release.json": release,
                    "protocol.json": protocol,
                    "protocol-qa.json": protocol_qa,
                    "latest.json": latest,
                }[name]

            with patch(MODULE + ".load_object", side_effect=loader), patch(
                MODULE + ".sha256_file", return_value="h" * 64
            ), patch(MODULE + ".verify_protocol", return_value={"errors": []}):
                return verify(release_path)

    def test_release_bound_to_latest_request_plus_24_hours_passes(self) -> None:
        result = self._run("2026-10-25T00:00:00+07:00")
        self.assertEqual(result["status"], PASS_STATUS, result["errors"])
        self.assertEqual(result["errors"], [])

    def test_release_shorter_than_latest_request_cooldown_fails(self) -> None:
        result = self._run("2026-10-24T23:59:59+07:00")
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("shorter" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
