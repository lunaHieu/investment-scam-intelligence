import json
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from scripts.execute_sec_edgar_iapd_wayback_availability_v1 import RateLimitStop
from scripts.retry_sec_edgar_iapd_wayback_availability_v8 import execute, validate_release


ROOT = Path(__file__).resolve().parents[1]
REAL_RELEASE = ROOT / "configs" / "sec_edgar_iapd_wayback_availability_retry_release_v8.json"
MODULE = "scripts.retry_sec_edgar_iapd_wayback_availability_v8"


def row(identifier: str, error: str | None) -> dict:
    return {
        "availability_plan_id": identifier,
        "shortlist_id": "SHORT-" + identifier,
        "cohort": "DEVELOPMENT",
        "candidate_host": identifier + ".example",
        "candidate_url": "https://" + identifier + ".example/",
        "query_timestamp": "20261003",
        "queried": True,
        "available": False if error is None else None,
        "snapshot_timestamp": None,
        "snapshot_url": None,
        "snapshot_http_status": None,
        "error": error,
    }


class RetrySecEdgarIapdWaybackAvailabilityV8Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.release_path = self.root / "release.json"
        self.release_path.write_text("{}\n", encoding="utf-8")
        self.output = self.root / "availability_report_v8.json"
        self.partial = self.output.with_suffix(self.output.suffix + ".partial")
        self.release = {
            "release_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_RETRY_RELEASE_V8",
            "inputs": {
                "partial_report_v7": {"path": "parent.json", "sha256": "a" * 64},
                "availability_plan": {"path": "plan.jsonl", "sha256": "b" * 64},
            },
            "cooldown_contract": {"not_before": "2026-10-20T14:06:35+07:00"},
            "retry_contract": {
                "endpoint": "https://archive.org/wayback/available",
                "target_timestamp": "20261003",
                "allowed_network_hosts": ["archive.org", "web.archive.org"],
                "minimum_delay_seconds": 60.0,
            },
            "planned_output": {
                "path": str(self.output),
                "report_id": "ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_AVAILABILITY_REPORT_V8",
            },
        }
        self.prior = {
            "cumulative_network_request_count": 164,
            "results": [row("resolved", None), row("retry-a", "old-a"), row("retry-b", "old-b")],
        }
        self.now = datetime.fromisoformat("2026-10-20T14:06:35+07:00")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _validation_patch(self):
        return patch(MODULE + ".validate_release", return_value=(deepcopy(self.release), deepcopy(self.prior)))

    @staticmethod
    def _success(_url, _contract, counter):
        counter[0] += 1
        return {"archived_snapshots": {}}

    def test_real_release_is_exact_two_row_retry_after_24_hours(self) -> None:
        release, prior = validate_release(REAL_RELEASE)
        parent = datetime.fromisoformat(prior["created_at"])
        not_before = datetime.fromisoformat(release["cooldown_contract"]["not_before"])
        self.assertEqual((not_before - parent).total_seconds(), 86400)
        self.assertEqual(release["retry_contract"]["minimum_delay_seconds"], 60.0)
        self.assertEqual(
            release["prior_outcome_contract"]["ordered_unresolved_availability_plan_ids"],
            [row["availability_plan_id"] for row in prior["results"] if row["error"] is not None],
        )

    def test_pre_gate_fails_before_reservation(self) -> None:
        with self._validation_patch():
            with self.assertRaises(PermissionError):
                execute(self.release_path, datetime.fromisoformat("2026-10-20T14:06:34+07:00"))
        self.assertFalse(self.partial.exists())
        self.assertFalse(self.output.exists())

    def test_crash_after_first_request_leaves_non_resumable_checkpoint(self) -> None:
        def crash(_checkpoint):
            raise RuntimeError("simulated process crash")

        with self._validation_patch(), patch(MODULE + ".fetch_json", side_effect=self._success):
            with self.assertRaisesRegex(RuntimeError, "simulated process crash"):
                execute(self.release_path, self.now, after_checkpoint=crash)
        journal = json.loads(self.partial.read_text(encoding="utf-8"))
        self.assertEqual(journal["status"], "PARTIAL_DO_NOT_AUTO_RESUME")
        self.assertFalse(journal["resume_allowed"])
        self.assertEqual(journal["attempted_availability_plan_ids"], ["retry-a"])
        self.assertEqual(journal["pending_availability_plan_ids"], ["retry-b"])

    def test_existing_partial_or_final_fails_closed_without_network(self) -> None:
        self.partial.write_text("reservation\n", encoding="utf-8")
        with self._validation_patch(), patch(MODULE + ".fetch_json") as fetcher:
            with self.assertRaises(FileExistsError):
                execute(self.release_path, self.now)
            fetcher.assert_not_called()
        self.partial.unlink()
        self.output.write_text("final\n", encoding="utf-8")
        with self._validation_patch(), patch(MODULE + ".fetch_json") as fetcher:
            with self.assertRaises(FileExistsError):
                execute(self.release_path, self.now)
            fetcher.assert_not_called()

    def test_http_429_is_checkpointed_and_stops(self) -> None:
        def rate_limited(_url, _contract, counter):
            counter[0] += 1
            raise RateLimitStop("mock 429")

        with self._validation_patch(), patch(MODULE + ".fetch_json", side_effect=rate_limited) as fetcher:
            report = execute(self.release_path, self.now)
        self.assertEqual(fetcher.call_count, 1)
        self.assertTrue(report["stopped_on_http_429"])
        self.assertEqual(report["retried_availability_plan_ids"], ["retry-a"])
        second = next(item for item in report["results"] if item["availability_plan_id"] == "retry-b")
        self.assertEqual(second["error"], "NOT_REQUERIED_AFTER_HTTP_429_STOP_V8")

    def test_happy_path_preserves_resolved_row_and_finalizes_atomically(self) -> None:
        preserved = deepcopy(self.prior["results"][0])
        with self._validation_patch(), patch(MODULE + ".fetch_json", side_effect=self._success) as fetcher:
            report = execute(self.release_path, self.now)
        self.assertEqual(fetcher.call_count, 2)
        self.assertEqual(report["status"], "COMPLETE")
        self.assertEqual(report["logical_retry_attempt_count"], 2)
        self.assertEqual(report["network_request_count_this_attempt"], 2)
        self.assertEqual(report["results"][0], preserved)
        self.assertTrue(self.output.is_file())
        self.assertFalse(self.partial.exists())


if __name__ == "__main__":
    unittest.main()
