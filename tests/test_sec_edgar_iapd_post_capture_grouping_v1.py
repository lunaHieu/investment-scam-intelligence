import json
import tempfile
import unittest
from pathlib import Path

from scripts.analyze_sec_edgar_iapd_post_capture_grouping_v1 import execute
from scripts.build_sec_edgar_iapd_grouping_release_v1 import build_release
from scripts.extract_sec_edgar_iapd_exact_text_v1 import execute as execute_extraction
from scripts.verify_sec_edgar_iapd_grouping_release_v1 import verify as verify_release
from scripts.verify_sec_edgar_iapd_exact_text_result_v1 import verify as verify_text
from scripts.verify_sec_edgar_iapd_post_capture_grouping_v1 import verify as verify_result
from tests import test_sec_edgar_iapd_exact_text_v1 as text_helpers


OPENED_INDEX = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_preacquisition\opened_external_exclusion_index_v1.json")
LEGACY_REMEDIATION = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_legacy_group_remediation_v1\legacy_group_remediation_map_v1.json")


class SecEdgarIapdPostCaptureGroupingV1Tests(unittest.TestCase):
    def make_release(self, directory: Path) -> tuple[Path, Path, Path]:
        helper = text_helpers.SecEdgarIapdExactTextV1Tests()
        text_release, text_release_qa, release = helper.make_release(directory)
        execute_extraction(text_release, text_release_qa)
        text_qa = verify_text(text_release, text_release_qa)
        text_qa_path = directory / "exact_text_result_qa.json"
        text_qa_path.write_text(json.dumps(text_qa, indent=2) + "\n", encoding="utf-8")
        output = directory / "grouping_analysis.json"
        grouping_release = build_release(
            manifest_path=Path(release["outputs"]["manifest"]),
            text_qa_path=text_qa_path,
            opened_index_path=OPENED_INDEX,
            legacy_remediation_path=LEGACY_REMEDIATION,
            output_path=output,
            created_at="2026-10-14T01:20:00+07:00",
        )
        release_path = directory / "grouping_release.json"
        release_path.write_text(json.dumps(grouping_release, indent=2) + "\n", encoding="utf-8")
        release_qa = verify_release(release_path)
        release_qa_path = directory / "grouping_release_qa.json"
        release_qa_path.write_text(json.dumps(release_qa, indent=2) + "\n", encoding="utf-8")
        return release_path, release_qa_path, output

    def test_grouping_reproduces_and_protects_holdout_collision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            release_path, release_qa_path, output = self.make_release(Path(tmp))
            result = execute(release_path, release_qa_path)
            self.assertTrue(output.is_file())
            self.assertEqual(result["counts"]["manifest_rows"], 2)
            self.assertEqual(result["counts"]["cross_cohort_groups"], 1)
            holdout = next(row for row in result["records"] if row["cohort"] == "EXTERNAL_HOLDOUT")
            self.assertEqual(holdout["routing_decision"], "EXCLUDED_HOLDOUT_CROSS_COHORT_COLLISION")
            qa = verify_result(release_path, release_qa_path)
            self.assertEqual(qa["status"], "PASS_GROUPING_REPRODUCED_MANUAL_GROUP_REVIEW_MAY_BE_PREPARED")
            self.assertFalse(qa["decision"]["primary_label_review_allowed"])


if __name__ == "__main__":
    unittest.main()
