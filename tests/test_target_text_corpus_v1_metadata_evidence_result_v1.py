import unittest

from scripts.verify_target_text_corpus_v1_metadata_evidence_result_v1 import verify_result


class MetadataEvidenceResultV1Tests(unittest.TestCase):
    def test_result_recomputes_all_21_evidence_items(self) -> None:
        self.assertEqual(
            verify_result(),
            {"status":"PASS_METADATA_EVIDENCE_RESULT_VERIFIED","branches":3,"evidence_items":21,"resolved":3,"partial":15,"unresolved":3,"acquisition_ready_sources":0},
        )


if __name__ == "__main__":
    unittest.main()
