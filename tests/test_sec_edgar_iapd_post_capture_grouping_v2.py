import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.analyze_sec_edgar_iapd_post_capture_grouping_v2 import execute
from scripts.build_sec_edgar_iapd_grouping_release_v2 import build_release
from scripts.verify_sec_edgar_iapd_grouping_release_v2 import verify as verify_release
from scripts.verify_sec_edgar_iapd_post_capture_grouping_v2 import verify as verify_result
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


OPENED_INDEX = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_preacquisition\opened_external_exclusion_index_v1.json")
LEGACY_REMEDIATION = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_legacy_group_remediation_v1\legacy_group_remediation_map_v1.json")
TEXT_QA_STATUS = "PASS_CAPTURED_SUBSET_EXACT_TEXT_BYTES_REGENERATED_GROUPING_MAY_BE_PREPARED"


class SecEdgarIapdPostCaptureGroupingV2Tests(unittest.TestCase):
    def test_subset_grouping_reproduces_routes_and_preserves_quarantine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            texts = directory / "texts"
            texts.mkdir()
            shared = "independent investment adviser disclosure content " * 8
            contents = [shared, shared] + [f"distinct adviser corpus token{chr(97 + index % 26)}{chr(97 + index // 26)} " * 8 for index in range(54)] + [""]
            rows = []
            for index, content in enumerate(contents):
                path = texts / f"R-{index}.txt"
                payload = content.encode("utf-8")
                path.write_bytes(payload)
                rows.append({
                    "record_id": f"R-{index}",
                    "shortlist_id": f"S-{index}",
                    "cohort": "EXTERNAL_HOLDOUT" if index == 1 else "DEVELOPMENT",
                    "candidate_host": f"host-{index}.example",
                    "raw_capture_sha256": hashlib.sha256(f"raw-{index}".encode()).hexdigest(),
                    "text_path": str(path.resolve()),
                    "text_sha256": hashlib.sha256(payload).hexdigest(),
                    "minimum_content_passed": index != 56,
                })
            manifest = directory / "manifest.jsonl"
            manifest.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            text_qa = {
                "status": TEXT_QA_STATUS,
                "inputs": {"manifest_sha256": sha256_file(manifest)},
                "checks": {"independently_regenerated_count": 57, "minimum_content_passed_count": 56, "quarantined_rows": 1},
                "decision": {"post_capture_grouping_may_be_prepared": True},
            }
            text_qa_path = directory / "text-qa.json"
            text_qa_path.write_text(json.dumps(text_qa, indent=2) + "\n", encoding="utf-8")
            output = directory / "analysis.json"
            release = build_release(
                manifest_path=manifest,
                text_qa_path=text_qa_path,
                opened_index_path=OPENED_INDEX,
                legacy_remediation_path=LEGACY_REMEDIATION,
                output_path=output,
                created_at="2026-10-21T23:50:00+07:00",
            )
            release_path = directory / "release.json"
            release_path.write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
            release_qa = verify_release(release_path)
            self.assertEqual(release_qa["status"], "PASS_OFFLINE_CAPTURED_SUBSET_GROUPING_RELEASE")
            release_qa_path = directory / "release-qa.json"
            release_qa_path.write_text(json.dumps(release_qa, indent=2) + "\n", encoding="utf-8")
            result = execute(release_path, release_qa_path)
            self.assertEqual(result["counts"]["manifest_rows"], 57)
            self.assertEqual(result["counts"]["minimum_content_pass_rows"], 56)
            self.assertGreaterEqual(result["counts"]["cross_cohort_groups"], 1)
            holdout = next(row for row in result["records"] if row["cohort"] == "EXTERNAL_HOLDOUT")
            self.assertEqual(holdout["routing_decision"], "EXCLUDED_HOLDOUT_CROSS_COHORT_COLLISION")
            below = next(row for row in result["records"] if not row["minimum_content_passed"])
            self.assertEqual(below["routing_decision"], "NOT_REVIEWABLE_BELOW_MINIMUM")
            qa = verify_result(release_path, release_qa_path)
            self.assertEqual(qa["status"], "PASS_CAPTURED_SUBSET_GROUPING_REPRODUCED_MANUAL_GROUP_REVIEW_MAY_BE_PREPARED")
            self.assertTrue(qa["decision"]["failed_capture_row_remains_quarantined"])


if __name__ == "__main__":
    unittest.main()
