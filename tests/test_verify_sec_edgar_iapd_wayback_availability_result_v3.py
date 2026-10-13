import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from scripts.verify_sec_edgar_iapd_wayback_availability_result_v3 import EXPECTED_SAFETY, pass_status, verify
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "sec_edgar_iapd_wayback_availability_retry_release_v3.json"
RELEASE_DATA = load_object(RELEASE)
V2 = Path(RELEASE_DATA["inputs"]["partial_report_v2"]["path"])


def complete_report() -> dict:
    prior = load_object(V2)
    results = []
    retried = []
    for row in prior["results"]:
        if row["error"] is None:
            results.append(deepcopy(row))
        else:
            retried.append(row["availability_plan_id"])
            results.append({
                **{key: row[key] for key in ("availability_plan_id", "shortlist_id", "cohort", "candidate_host", "candidate_url", "query_timestamp")},
                "queried": True,
                "available": False,
                "snapshot_timestamp": None,
                "snapshot_url": None,
                "snapshot_http_status": None,
                "error": None,
            })
    return {
        "report_id": "ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_AVAILABILITY_REPORT_V3",
        "created_at": RELEASE_DATA["cooldown_contract"]["not_before"],
        "status": "COMPLETE",
        "release_sha256": sha256_file(RELEASE),
        "parent_report_sha256": sha256_file(V2),
        "plan_sha256": RELEASE_DATA["inputs"]["availability_plan"]["sha256"],
        "requested_candidate_count": 115,
        "resolved_results_reused_from_v2": 45,
        "retry_candidate_count": 70,
        "retried_availability_plan_ids": retried,
        "network_request_count_this_attempt": 70,
        "cumulative_network_request_count": 123,
        "available_snapshot_count": 26,
        "unavailable_snapshot_count": 89,
        "unresolved_error_count": 0,
        "stopped_on_http_429": False,
        "capture_plan_construction_ready": True,
        "results": results,
        "safety_contract": EXPECTED_SAFETY,
    }


class VerifySecEdgarIapdWaybackAvailabilityResultV3Tests(unittest.TestCase):
    def test_complete_result_passes_and_opens_only_capture_plan_preparation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "v3.json"
            path.write_text(json.dumps(complete_report(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            result = verify(RELEASE, V2, path)
        self.assertEqual(result["status"], "PASS_COMPLETE_CAPTURE_PLAN_MAY_BE_PREPARED")
        self.assertTrue(result["checks"]["capture_plan_construction_ready"])
        self.assertEqual(result["checks"]["resolved_results"], 115)
        self.assertEqual(result["errors"], [])

    def test_changed_resolved_parent_row_fails(self) -> None:
        report = complete_report()
        report["results"][0]["available"] = True
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "v3.json"
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            result = verify(RELEASE, V2, path)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("Resolved V2 result changed" in error for error in result["errors"]))

    def test_partial_pass_status_keeps_capture_plan_blocked(self) -> None:
        self.assertEqual(pass_status(1), "PASS_PARTIAL_ERRORS_PRESERVED_CAPTURE_PLAN_BLOCKED")


if __name__ == "__main__":
    unittest.main()
