import unittest

from scripts.verify_target_text_corpus_v1_public_metadata_gap_resolution_release_v1 import verify


class PublicMetadataGapResolutionReleaseV1Tests(unittest.TestCase):
    def test_release_is_finite_new_pages_only_and_nonacquiring(self) -> None:
        result = verify()
        self.assertEqual(result["status"], "PASS_PUBLIC_METADATA_GAP_RELEASE_VERIFIED")
        self.assertEqual((result["tasks"], result["pages"], result["queries"]), (4, 7, 1))


if __name__ == "__main__":
    unittest.main()
