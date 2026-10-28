import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_ready_channel_capture_continuation_release_v2 import PASS_STATUS, verify


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "target_text_corpus_v1_ready_channel_capture_continuation_release_v2.json"


class ContinuationReleaseV2Tests(unittest.TestCase):
    def test_real_release_is_exact_48_and_verified(self):
        result = verify(RELEASE)
        self.assertEqual(result["status"], PASS_STATUS, result["errors"])
        self.assertEqual(result["checks"]["record_count"], 48)
        self.assertTrue(result["checks"]["planned_output_absent"])

    def test_row_local_quarantine_does_not_relax_provider_failure_stop(self):
        result = verify(RELEASE)
        self.assertTrue(result["checks"]["row_local_quarantine_continuation"])


if __name__ == "__main__":
    unittest.main()
