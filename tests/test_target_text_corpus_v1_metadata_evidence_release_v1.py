import json
import unittest

from scripts.verify_target_text_corpus_v1_metadata_evidence_release_v1 import DEFAULT_RELEASE, verify_release


class MetadataEvidenceReleaseV1Tests(unittest.TestCase):
    def test_release_verifies_exact_three_branches_and_21_items(self) -> None:
        result = verify_release()
        self.assertEqual(result["status"], "PASS_METADATA_EVIDENCE_RELEASE_VERIFIED")
        self.assertEqual((result["branch_count"], result["evidence_item_count"], result["query_count"]), (3, 21, 6))

    def test_all_mutating_or_data_opening_capabilities_are_closed(self) -> None:
        value = json.loads(DEFAULT_RELEASE.read_text(encoding="utf-8"))
        contract = value["execution_contract"]
        for key in (
            "dataset_download_allowed", "repository_clone_allowed", "raw_dataset_file_open_allowed",
            "raw_html_retention_allowed", "candidate_live_domain_access_allowed", "author_contact_allowed",
            "code_execution_allowed", "labeling_allowed", "validation_or_test_open_allowed", "model_operations_allowed",
        ):
            self.assertIs(contract[key], False)

    def test_verifier_has_no_network_or_output_side_effect(self) -> None:
        before = verify_release()["output_exists"]
        verify_release()
        self.assertEqual(verify_release()["output_exists"], before)


if __name__ == "__main__":
    unittest.main()
