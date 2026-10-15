import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from scripts.verify_sec_edgar_iapd_wayback_availability_result_v4 import EXPECTED_SAFETY
from scripts.verify_sec_edgar_iapd_wayback_availability_result_v5 import verify
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "sec_edgar_iapd_wayback_availability_retry_release_v5.json"
RELEASE_DATA = load_object(RELEASE)
V4 = Path(RELEASE_DATA["inputs"]["partial_report_v4"]["path"])


def complete_report() -> dict:
    prior = load_object(V4)
    results = []
    retried = []
    for row in prior["results"]:
        if row["error"] is None:
            results.append(deepcopy(row))
        else:
            retried.append(row["availability_plan_id"])
            results.append({**{key: row[key] for key in ("availability_plan_id", "shortlist_id", "cohort", "candidate_host", "candidate_url", "query_timestamp")}, "queried": True, "available": False, "snapshot_timestamp": None, "snapshot_url": None, "snapshot_http_status": None, "error": None})
    return {
        "report_id": "ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_AVAILABILITY_REPORT_V5",
        "created_at": RELEASE_DATA["cooldown_contract"]["not_before"],
        "status": "COMPLETE",
        "release_sha256": sha256_file(RELEASE),
        "parent_report_sha256": sha256_file(V4),
        "plan_sha256": RELEASE_DATA["inputs"]["availability_plan"]["sha256"],
        "requested_candidate_count": 115,
        "resolved_results_reused_from_v4": 92,
        "retry_candidate_count": 23,
        "retried_availability_plan_ids": retried,
        "network_request_count_this_attempt": 23,
        "cumulative_network_request_count": 156,
        "available_snapshot_count": 45,
        "unavailable_snapshot_count": 70,
        "unresolved_error_count": 0,
        "stopped_on_http_429": False,
        "capture_plan_construction_ready": True,
        "results": results,
        "safety_contract": EXPECTED_SAFETY,
    }


class VerifySecEdgarIapdWaybackAvailabilityResultV5Tests(unittest.TestCase):
    def test_complete_result_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "v5.json"
            path.write_text(json.dumps(complete_report()), encoding="utf-8")
            result = verify(RELEASE, V4, path)
        self.assertEqual(result["status"], "PASS_COMPLETE_CAPTURE_PLAN_MAY_BE_PREPARED")
        self.assertEqual(result["checks"]["resolved_results"], 115)
        self.assertEqual(result["errors"], [])

    def test_changed_resolved_parent_row_fails(self) -> None:
        report = complete_report()
        report["results"][0]["available"] = True
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "v5.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            result = verify(RELEASE, V4, path)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("Resolved V4 result changed" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
