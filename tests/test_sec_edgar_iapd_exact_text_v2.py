import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_sec_edgar_iapd_captured_subset_v1 import VIEW_ID, VIEW_STATUS
from scripts.build_sec_edgar_iapd_exact_text_release_v2 import build_release
from scripts.extract_sec_edgar_iapd_exact_text_v2 import execute
from scripts.verify_sec_edgar_iapd_captured_subset_v1 import QA_ID as SUBSET_QA_ID, QA_STATUS as SUBSET_QA_STATUS
from scripts.verify_sec_edgar_iapd_exact_text_release_v2 import verify as verify_release
from scripts.verify_sec_edgar_iapd_exact_text_result_v2 import verify as verify_result
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


class SecEdgarIapdExactTextV2Tests(unittest.TestCase):
    def test_captured_subset_extracts_and_regenerates_without_quarantined_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            rows = []
            payloads = [
                b"<html><body>Long investment advisory content for testing.</body></html>",
                b"<html><body>x</body></html>",
            ]
            for index, payload in enumerate(payloads):
                raw = directory / f"raw-{index}.html"
                raw.write_bytes(payload)
                rows.append({
                    "availability_plan_id": f"AP-{index}",
                    "shortlist_id": f"SL-{index}",
                    "cohort": "DEVELOPMENT" if index == 0 else "EXTERNAL_HOLDOUT",
                    "candidate_host": f"example{index}.test",
                    "candidate_url": f"https://example{index}.test/",
                    "snapshot_timestamp": "20261001000000",
                    "snapshot_url": f"https://web.archive.org/web/20261001000000/https://example{index}.test/",
                    "requested_archive_url": f"https://web.archive.org/web/20261001000000id_/https://example{index}.test/",
                    "capture_path": str(raw),
                    "outcome": "CAPTURED",
                    "final_archive_url": f"https://web.archive.org/web/20261001000000id_/https://example{index}.test/",
                    "redirect_count": 0,
                    "http_status": 200,
                    "content_type": "text/html",
                    "bytes": len(payload),
                    "sha256": sha256_file(raw),
                    "error": None,
                })
            view = {
                "report_id": VIEW_ID,
                "status": VIEW_STATUS,
                "source_population_count": 3,
                "captured_count": 2,
                "quarantined_count": 1,
                "ordered_quarantined_rows": [{"availability_plan_id": "AP-2"}],
                "results": rows,
                "decision": {"quarantined_rows_included": False},
            }
            view_path = directory / "subset.json"
            view_path.write_text(json.dumps(view, indent=2) + "\n", encoding="utf-8")
            subset_qa = {
                "verification_id": SUBSET_QA_ID,
                "status": SUBSET_QA_STATUS,
                "inputs": {"view_sha256": sha256_file(view_path)},
                "decision": {"offline_exact_text_release_may_be_prepared": True},
                "errors": [],
            }
            subset_qa_path = directory / "subset-qa.json"
            subset_qa_path.write_text(json.dumps(subset_qa, indent=2) + "\n", encoding="utf-8")
            text_root = directory / "texts"
            manifest = directory / "manifest.jsonl"
            report_path = directory / "report.json"
            release = build_release(
                subset_view_path=view_path,
                subset_qa_path=subset_qa_path,
                text_root=text_root,
                manifest_path=manifest,
                report_path=report_path,
                created_at="2026-10-21T23:40:00+07:00",
            )
            release_path = directory / "release.json"
            release_path.write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
            release_qa = verify_release(release_path)
            self.assertEqual(release_qa["status"], "PASS_OFFLINE_CAPTURED_SUBSET_EXACT_TEXT_RELEASE_V2")
            release_qa_path = directory / "release-qa.json"
            release_qa_path.write_text(json.dumps(release_qa, indent=2) + "\n", encoding="utf-8")
            report = execute(release_path, release_qa_path)
            self.assertEqual(report["counts"]["extracted_count"], 2)
            self.assertEqual(report["counts"]["minimum_content_passed_count"], 1)
            self.assertEqual(report["counts"]["below_minimum_preserved_count"], 1)
            result = verify_result(release_path, release_qa_path)
            self.assertEqual(result["status"], "PASS_CAPTURED_SUBSET_EXACT_TEXT_BYTES_REGENERATED_GROUPING_MAY_BE_PREPARED")
            self.assertEqual(result["checks"]["byte_for_byte_match_count"], 2)
            self.assertEqual(result["checks"]["quarantined_rows"], 1)


if __name__ == "__main__":
    unittest.main()
