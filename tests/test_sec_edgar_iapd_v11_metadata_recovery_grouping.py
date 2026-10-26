import json
import tempfile
import unittest
from pathlib import Path

from scripts.analyze_sec_edgar_iapd_v11_metadata_recovery_grouping import execute
from scripts.build_sec_edgar_iapd_v11_metadata_recovery_grouping_release import build_release
from scripts.extract_sec_edgar_iapd_v11_metadata_recovery_exact_text import execute as execute_text
from scripts.verify_sec_edgar_iapd_v11_metadata_recovery_exact_text_result import verify as verify_text
from scripts.verify_sec_edgar_iapd_v11_metadata_recovery_grouping_release import PASS_STATUS as RELEASE_PASS, verify as verify_release
from scripts.verify_sec_edgar_iapd_v11_metadata_recovery_grouping_result import PASS_STATUS as RESULT_PASS, verify as verify_result
from tests.test_sec_edgar_iapd_v11_metadata_recovery_exact_text import V11MetadataRecoveryExactTextTests


OPENED_INDEX = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_preacquisition\opened_external_exclusion_index_v1.json")
LEGACY_REMEDIATION = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_legacy_group_remediation_v1\legacy_group_remediation_map_v1.json")


class V11MetadataRecoveryGroupingTests(unittest.TestCase):
    def test_grouping_is_reproduced_without_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            text_helper = V11MetadataRecoveryExactTextTests()
            text_release, text_release_qa, text_release_data = text_helper._fixture(root)
            execute_text(text_release, text_release_qa)
            text_qa = verify_text(text_release, text_release_qa)
            text_qa_path = root / "text_result_qa.json"
            text_qa_path.write_text(json.dumps(text_qa), encoding="utf-8")
            output = root / "grouping.json"
            release = build_release(manifest_path=Path(text_release_data["outputs"]["manifest"]), text_qa_path=text_qa_path, opened_index_path=OPENED_INDEX, legacy_remediation_path=LEGACY_REMEDIATION, output_path=output, created_at="2026-10-27T09:10:00+07:00")
            release_path = root / "grouping_release.json"
            release_path.write_text(json.dumps(release), encoding="utf-8")
            release_qa = verify_release(release_path)
            self.assertEqual(release_qa["status"], RELEASE_PASS, release_qa["errors"])
            release_qa_path = root / "grouping_release_qa.json"
            release_qa_path.write_text(json.dumps(release_qa), encoding="utf-8")
            result = execute(release_path, release_qa_path)
            self.assertEqual(result["counts"]["manifest_rows"], 2)
            self.assertEqual(result["counts"]["labels_created"], 0)
            qa = verify_result(release_path, release_qa_path)
            self.assertEqual(qa["status"], RESULT_PASS, qa["errors"])
            self.assertTrue(qa["decision"]["manual_group_review_may_be_prepared"])
            self.assertFalse(qa["decision"]["primary_label_review_allowed"])


if __name__ == "__main__":
    unittest.main()
