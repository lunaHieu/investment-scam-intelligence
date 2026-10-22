import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from scripts.verify_sec_edgar_iapd_wayback_availability_result_v11 import verify


MODULE = "scripts.verify_sec_edgar_iapd_wayback_availability_result_v11"
IDS = ["TTCV1_EDGAR_AVAIL_HOLDOUT_011", "TTCV1_EDGAR_AVAIL_HOLDOUT_018"]


def base_row(identifier: str, index: int, *, error=None) -> dict:
    return {
        "availability_plan_id": identifier,
        "shortlist_id": f"SHORT-{index}",
        "cohort": "EXTERNAL_HOLDOUT" if identifier in IDS else "DEVELOPMENT",
        "candidate_host": f"host-{index}.example",
        "candidate_url": f"https://host-{index}.example/",
        "query_timestamp": "20261003",
        "queried": error is None,
        "available": False if error is None else None,
        "snapshot_timestamp": None,
        "snapshot_url": None,
        "snapshot_http_status": None,
        "error": error,
    }


class AvailabilityV11ResultVerifierTests(unittest.TestCase):
    def test_complete_exact_two_row_result_passes_without_mutating_parent(self) -> None:
        parent_rows = [base_row(f"RESOLVED_{index:03d}", index) for index in range(113)]
        parent_rows.extend(
            [
                base_row(IDS[0], 113, error="old-429"),
                base_row(IDS[1], 114, error="old-not-queried"),
            ]
        )
        current_rows = deepcopy(parent_rows[:113])
        for index, identifier in enumerate(IDS, start=113):
            current_rows.append(base_row(identifier, index))
            current_rows[-1]["queried"] = True
            current_rows[-1]["response_diagnostics"] = {
                "http_status": 200,
                "response_headers": {"Content-Type": "application/json"},
            }
        release = {
            "inputs": {"protocol": {"path": "configs/protocol.json"}},
            "cooldown_contract": {"not_before": "2026-10-25T00:00:00+07:00"},
            "network_contract": {"maximum_redirects": 3},
        }
        protocol = {"inputs": {"availability_report_v10": {"path": "parent.json"}}}
        parent = {"cumulative_network_request_count": 168, "results": parent_rows}
        qa = {"release": {"sha256": "h" * 64}, "errors": []}
        report = {
            "report_id": "ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_AVAILABILITY_REPORT_V11",
            "created_at": "2026-10-25T00:00:00+07:00",
            "status": "COMPLETE",
            "executor": "scripts.retry_sec_edgar_iapd_wayback_availability_v11",
            "release_sha256": "h" * 64,
            "release_qa_sha256": "h" * 64,
            "requested_candidate_count": 115,
            "resolved_results_reused_from_v10": 113,
            "retry_candidate_count": 2,
            "retried_availability_plan_ids": IDS,
            "logical_retry_attempt_count": 2,
            "network_request_count_this_attempt": 2,
            "cumulative_network_request_count": 170,
            "available_snapshot_count": 0,
            "unavailable_snapshot_count": 115,
            "unresolved_error_count": 0,
            "stopped_on_http_429": False,
            "supplemental_availability_complete": True,
            "original_capture_plan_mutation_allowed": False,
            "results": current_rows,
            "safety_contract": {
                "candidate_live_domain_access_operations": 0,
                "only_archive_availability_hosts_accessed": True,
                "archived_page_download_operations": 0,
                "artifact_captures": 0,
                "labels_created": 0,
                "model_operations": 0,
                "training_allowed": False,
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release_path = root / "configs" / "release.json"
            qa_path = root / "qa.json"
            report_path = root / "report.json"
            for path in (release_path, qa_path, report_path):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}", encoding="utf-8")

            def loader(path):
                text = str(path)
                if text.endswith("release.json"):
                    return release
                if text.endswith("qa.json"):
                    return qa
                if text.endswith("report.json"):
                    return report
                if text.endswith("protocol.json"):
                    return protocol
                if text.endswith("parent.json"):
                    return parent
                raise AssertionError(text)

            with patch(MODULE + ".load_object", side_effect=loader), patch(
                MODULE + ".sha256_file", return_value="h" * 64
            ):
                result = verify(release_path, qa_path, report_path)
        self.assertEqual(
            result["status"],
            "PASS_COMPLETE_SUPPLEMENTAL_AVAILABILITY_RESULT_CAPTURE_PLAN_UNCHANGED",
            result["errors"],
        )
        self.assertEqual(result["errors"], [])
        self.assertTrue(result["checks"]["resolved_v10_results_preserved"])
        self.assertFalse(result["decision"]["original_capture_plan_may_be_mutated"])


if __name__ == "__main__":
    unittest.main()
