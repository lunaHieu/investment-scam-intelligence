import unittest

from scripts.verify_target_text_corpus_v1_public_metadata_gap_resolution_result_v1 import verify


class PublicMetadataGapResolutionResultV1Tests(unittest.TestCase):
    def test_forbidden_preview_is_fail_closed_and_release_consumed(self) -> None:
        self.assertEqual(verify(), {"status":"PASS_FAIL_CLOSED_RESULT_VERIFIED","tasks":4,"validly_advanced":0,"preview_exposure_pages":1,"files_acquired":0})


if __name__ == "__main__":
    unittest.main()
