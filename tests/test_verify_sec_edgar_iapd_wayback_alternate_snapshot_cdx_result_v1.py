import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_sec_edgar_iapd_wayback_alternate_snapshot_cdx_result_v1 import verify
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "sec_edgar_iapd_wayback_alternate_snapshot_cdx_release_v1.json"
RELEASE_QA = Path(
    r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs"
    r"\sec_edgar_iapd_alternate_snapshot_cdx_v1\independent_release_qa_v1.json"
)


class AlternateSnapshotCdxResultVerifierV1Tests(unittest.TestCase):
    def test_selected_candidate_is_independently_recomputed_without_authorizing_capture(self) -> None:
        release = json.loads(RELEASE.read_text(encoding="utf-8"))
        qa_hash = sha256_file(RELEASE_QA)
        fields = release["cdx_contract"]["query"]["fields"]
        eligible = {
            "timestamp": "20260209193325",
            "original": "https://lionpoint.com/",
            "statuscode": "200",
            "mimetype": "text/html",
            "digest": "A" * 32,
        }
        selected = {
            **eligible,
            "requested_archive_url": (
                "https://web.archive.org/web/20260209193325id_/https://lionpoint.com/"
            ),
            "selection_rank": 1,
        }
        report = {
            "report_id": release["planned_output"]["report_id"],
            "created_at": "2026-10-24T00:00:00+07:00",
            "status": "COMPLETE_ALTERNATE_CANDIDATE_SELECTED_CAPTURE_NOT_AUTHORIZED",
            "executor": "scripts.execute_sec_edgar_iapd_wayback_alternate_snapshot_cdx_v1",
            "release_sha256": sha256_file(RELEASE),
            "release_qa_sha256": qa_hash,
            "target_availability_plan_id": release["target_record"]["availability_plan_id"],
            "failed_snapshot_timestamp_excluded": "20260210193325",
            "network_request_count": 1,
            "stopped_on_http_429": False,
            "response_diagnostics": {},
            "error": None,
            "enumeration": {
                "returned_row_count": 1,
                "eligible_row_count": 1,
                "rejected_row_count": 0,
                "eligible_rows": [eligible],
                "rejected_rows": [],
                "selected_candidate": selected,
                "selection_rule": release["cdx_contract"]["selection_rule"],
            },
            "decision": {
                "alternate_capture_release_may_be_prepared": True,
                "alternate_capture_is_authorized": False,
                "same_failed_timestamp_may_be_used": False,
                "original_review_population_may_be_mutated": False,
                "training_allowed": False,
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.json"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            result = verify(
                RELEASE,
                RELEASE_QA,
                report_path,
                require_frozen_output_path=False,
            )
        self.assertEqual(
            result["status"],
            "PASS_ALTERNATE_CANDIDATE_SELECTED_SEPARATE_CAPTURE_RELEASE_MAY_BE_PREPARED",
            result["errors"],
        )
        self.assertTrue(result["checks"]["selected_candidate_recomputed"])
        self.assertFalse(result["decision"]["capture_authorized_by_this_qa"])


if __name__ == "__main__":
    unittest.main()
