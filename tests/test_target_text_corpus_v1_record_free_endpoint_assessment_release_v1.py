import json
import unittest

from scripts.record_free_endpoint_assessment_v1 import RELEASE, verify_release


class RecordFreeEndpointAssessmentReleaseV1Tests(unittest.TestCase):
    def test_exact_head_only_release(self) -> None:
        result = verify_release()
        self.assertEqual((result["status"], result["endpoints"], result["method"]), ("PASS_RECORD_FREE_ENDPOINT_RELEASE_VERIFIED", 8, "HEAD"))

    def test_no_body_or_data_capability(self) -> None:
        contract = json.loads(RELEASE.read_text(encoding="utf-8"))["execution_contract"]
        self.assertIs(contract["response_body_read_allowed"], False)
        self.assertIs(contract["dataset_landing_or_viewer_pages_allowed"], False)
        self.assertIs(contract["dataset_download_allowed"], False)


if __name__ == "__main__":
    unittest.main()
