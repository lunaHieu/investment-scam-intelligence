import json
import unittest
from unittest.mock import patch

from scripts.http_transport_target_text_corpus_v1_parser_bound_content_supplemental_v1 import (
    authorize_live_transport,
)
from scripts.verify_target_text_corpus_v1_parser_bound_content_release_v1 import ROOT
from scripts.verify_target_text_corpus_v1_parser_bound_content_supplemental_result_v1 import (
    DEFAULT_RESULT,
    verify_result,
)


class CurrentArtifactLifecycleV9Tests(unittest.TestCase):
    def setUp(self):
        self.value = json.loads(DEFAULT_RESULT.read_text(encoding="utf-8"))
        self.rows = {row["resource_id"]: row for row in self.value["resources"]}

    def test_supplemental_result_is_exact_and_independently_verified(self):
        verified = verify_result(DEFAULT_RESULT)
        self.assertEqual(verified["status"], "PASS_PARSER_BOUND_SUPPLEMENTAL_RESULT_VERIFIED")
        self.assertEqual(
            (verified["resources"], verified["success"], verified["parser_rejected"], verified["skipped_after_failure"]),
            (4, 2, 2, 0),
        )

    def test_pbc05_parser_failure_did_not_block_remaining_rows(self):
        self.assertEqual([row["resource_id"] for row in self.value["resources"]], ["PBC05", "PBC06", "PBC07", "PBC08"])
        self.assertEqual(self.rows["PBC05"]["outcome"], "PARSER_REJECTED")
        self.assertEqual(self.rows["PBC06"]["outcome"], "SUCCESS")
        self.assertEqual(self.rows["PBC07"]["outcome"], "SUCCESS")
        self.assertEqual(self.rows["PBC08"]["outcome"], "PARSER_REJECTED")

    def test_supplemental_result_retains_no_raw_or_temporary_artifacts(self):
        self.assertTrue(all(row["raw_response_retained"] is False for row in self.value["resources"]))
        self.assertEqual(self.value["safety_contract"]["dataset_files_downloaded"], 0)
        self.assertFalse((ROOT / "tmp" / "pdfs").exists() and list((ROOT / "tmp" / "pdfs").rglob("*")))
        self.assertFalse(DEFAULT_RESULT.with_name(DEFAULT_RESULT.name + ".partial").exists())
        self.assertFalse(DEFAULT_RESULT.with_name(DEFAULT_RESULT.name + ".partial.tmp").exists())

    def test_supplemental_rerun_is_blocked_before_transport(self):
        with patch(
            "scripts.http_transport_target_text_corpus_v1_parser_bound_content_supplemental_v1.urllib.request.build_opener"
        ) as opener:
            with self.assertRaises(PermissionError):
                authorize_live_transport()
            opener.assert_not_called()

    def test_supplemental_authorization_is_historical_and_downstream_gates_remain_closed(self):
        amendment_path = ROOT / "configs" / "target_text_corpus_v1_parser_bound_content_supplemental_execution_amendment_v1.json"
        amendment = json.loads(amendment_path.read_text(encoding="utf-8"))
        self.assertEqual(amendment["status"], "OWNER_AUTHORIZED_EXACT_PBC05_PBC08")
        self.assertTrue(DEFAULT_RESULT.is_file())
        self.assertFalse(self.value["decision"]["evidence_acceptance_allowed"])
        self.assertFalse(self.value["decision"]["dataset_acquisition_allowed"])
        self.assertFalse(self.value["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
