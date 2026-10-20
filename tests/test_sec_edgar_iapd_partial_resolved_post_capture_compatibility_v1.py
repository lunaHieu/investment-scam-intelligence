import copy
import hashlib
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from scripts.build_sec_edgar_iapd_exact_text_release_v1 import build_release as build_text_release
from scripts.build_sec_edgar_iapd_grouping_release_v1 import build_release as build_grouping_release
from scripts.extract_sec_edgar_iapd_exact_text_v1 import execute as execute_text
from scripts.verify_sec_edgar_iapd_exact_text_release_v1 import verify as verify_text_release
from scripts.verify_sec_edgar_iapd_exact_text_result_v1 import verify as verify_text_result
from scripts.verify_sec_edgar_iapd_grouping_release_v1 import verify as verify_grouping_release
from scripts.verify_sec_edgar_iapd_wayback_capture_result_v1 import verify as verify_capture
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


class SecEdgarIapdPartialResolvedPostCaptureCompatibilityV1Tests(unittest.TestCase):
    def test_v5_shaped_58_row_capture_passes_existing_post_capture_gates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            raw_root = directory / "raw"
            raw_root.mkdir()
            plan_rows = []
            result_rows = []
            cohorts = []
            for index in range(58):
                cohort = "DEVELOPMENT" if index < 46 else "EXTERNAL_HOLDOUT"
                cohorts.append(cohort)
                record_id = f"SYNTHETIC_V5_{index:03d}"
                archive_url = f"https://web.archive.org/web/202001{index + 1:08d}id_/https://example-{index}.invalid/"
                raw_path = raw_root / f"{record_id}.html"
                payload = (
                    f"<html><body>Reference profile {index} unique-token-{index} "
                    f"investment adviser registration information for compatibility.</body></html>"
                ).encode("utf-8")
                raw_path.write_bytes(payload)
                row = {
                    "availability_plan_id": record_id,
                    "shortlist_id": f"SHORT_{index:03d}",
                    "cohort": cohort,
                    "candidate_host": f"example-{index}.invalid",
                    "candidate_url": f"https://example-{index}.invalid/",
                    "snapshot_timestamp": f"202001{index + 1:08d}",
                    "snapshot_url": archive_url.replace("id_/", "/"),
                    "requested_archive_url": archive_url,
                    "capture_path": str(raw_path),
                }
                plan_rows.append(row)
                result_rows.append({
                    **copy.deepcopy(row),
                    "outcome": "CAPTURED",
                    "final_archive_url": archive_url,
                    "http_status": 200,
                    "content_type": "text/html; charset=utf-8",
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "error": None,
                })

            plan = {
                "report_id": "ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_CAPTURE_PLAN_V1",
                "status": "FROZEN_ALL_RESOLVED_AVAILABLE_V8_SNAPSHOTS_UNRESOLVED_QUARANTINED_UNLABELED",
                "tooling_version": "v5",
                "availability_generation": "v8",
                "source_candidate_count": 115,
                "planned_capture_count": 58,
                "planned_by_cohort": {"DEVELOPMENT": 46, "EXTERNAL_HOLDOUT": 12},
                "unresolved_candidates_quarantined": 2,
                "results": plan_rows,
            }
            plan_path = directory / "capture_plan_v5.json"
            plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
            report_path = directory / "capture_report_v1.json"
            release = {
                "release_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_CAPTURE_EXECUTION_RELEASE_V1",
                "tooling_version": "v5",
                "inputs": {"capture_plan": {"path": str(plan_path), "sha256": sha256_file(plan_path), "record_count": 58}},
                "planned_output": {"path": str(report_path), "report_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_CAPTURE_REPORT_V1"},
            }
            release_path = directory / "capture_release_v5.json"
            release_path.write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
            release_qa = {
                "status": "PASS_ARCHIVE_ONLY_CAPTURE_RELEASE",
                "release": {"sha256": sha256_file(release_path)},
            }
            release_qa_path = directory / "capture_release_qa_v5.json"
            release_qa_path.write_text(json.dumps(release_qa, indent=2) + "\n", encoding="utf-8")
            report = {
                "report_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_CAPTURE_REPORT_V1",
                "status": "COMPLETE",
                "release": {"sha256": sha256_file(release_path)},
                "release_qa": {"sha256": sha256_file(release_qa_path)},
                "planned_capture_count": 58,
                "captured_count": 58,
                "failed_count": 0,
                "not_attempted_count": 0,
                "captured_by_cohort": dict(Counter(cohorts)),
                "network_request_count": 58,
                "stopped_on_http_429": False,
                "results": result_rows,
            }
            report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

            capture_qa = verify_capture(release_path, release_qa_path, report_path)
            self.assertEqual(capture_qa["status"], "PASS_COMPLETE_TEXT_EXTRACTION_RELEASE_MAY_BE_PREPARED")
            self.assertEqual(capture_qa["checks"]["planned_capture_count"], 58)
            capture_qa_path = directory / "capture_result_qa.json"
            capture_qa_path.write_text(json.dumps(capture_qa, indent=2) + "\n", encoding="utf-8")

            text_root = directory / "exact_text" / "text"
            manifest_path = directory / "exact_text" / "manifest.jsonl"
            text_report_path = directory / "exact_text" / "report.json"
            text_release = build_text_release(
                capture_report_path=report_path,
                capture_qa_path=capture_qa_path,
                text_root=text_root,
                manifest_path=manifest_path,
                report_path=text_report_path,
                created_at="2026-10-20T22:30:00+07:00",
            )
            text_release_path = directory / "exact_text_release.json"
            text_release_path.write_text(json.dumps(text_release, indent=2) + "\n", encoding="utf-8")
            text_release_qa = verify_text_release(text_release_path)
            self.assertEqual(text_release_qa["status"], "PASS_OFFLINE_EXACT_TEXT_RELEASE")
            text_release_qa_path = directory / "exact_text_release_qa.json"
            text_release_qa_path.write_text(json.dumps(text_release_qa, indent=2) + "\n", encoding="utf-8")
            text_report = execute_text(text_release_path, text_release_qa_path)
            self.assertEqual(text_report["counts"]["extracted_count"], 58)
            self.assertEqual(text_report["counts"]["by_cohort"], {"DEVELOPMENT": 46, "EXTERNAL_HOLDOUT": 12})
            text_qa = verify_text_result(text_release_path, text_release_qa_path)
            self.assertEqual(text_qa["status"], "PASS_EXACT_TEXT_BYTES_REGENERATED_GROUPING_MAY_BE_PREPARED")
            self.assertEqual(text_qa["checks"]["independently_regenerated_count"], 58)
            text_qa_path = directory / "exact_text_result_qa.json"
            text_qa_path.write_text(json.dumps(text_qa, indent=2) + "\n", encoding="utf-8")

            opened_path = directory / "opened.json"
            opened_path.write_text(json.dumps({"counts": {"opened_records": 107}}) + "\n", encoding="utf-8")
            remediation_path = directory / "remediation.json"
            remediation_path.write_text(json.dumps({"counts": {"legacy_records": 86}}) + "\n", encoding="utf-8")
            grouping_release = build_grouping_release(
                manifest_path=manifest_path,
                text_qa_path=text_qa_path,
                opened_index_path=opened_path,
                legacy_remediation_path=remediation_path,
                output_path=directory / "grouping_analysis.json",
                created_at="2026-10-20T22:31:00+07:00",
            )
            grouping_release_path = directory / "grouping_release.json"
            grouping_release_path.write_text(json.dumps(grouping_release, indent=2) + "\n", encoding="utf-8")
            grouping_qa = verify_grouping_release(grouping_release_path)
            self.assertEqual(grouping_qa["status"], "PASS_OFFLINE_GROUPING_RELEASE")
            self.assertEqual(grouping_qa["checks"]["manifest_rows"], 58)
            self.assertFalse(grouping_qa["decision"]["human_label_review_allowed"])


if __name__ == "__main__":
    unittest.main()
