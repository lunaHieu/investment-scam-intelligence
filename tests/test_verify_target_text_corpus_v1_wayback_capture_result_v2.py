import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_wayback_capture_result_v2 import verify


PILOT = Path(
    r"D:\nckh 2026-2027\ISI_Data\curated\target_text_corpus_v1_schema_review_pilot"
)


class TargetTextCorpusWaybackCaptureResultV2Tests(unittest.TestCase):
    def test_capture_result_passes_independent_audit(self) -> None:
        result = verify(
            plan_path=PILOT / "wayback_capture_plan_v1.json",
            v1_path=PILOT / "wayback_capture_report_v1.json",
            v2_path=PILOT / "wayback_capture_report_v2.json",
        )
        self.assertFalse(result["errors"], result["errors"])
        self.assertEqual(result["checks"]["captured_count"], 23)
        self.assertEqual(result["checks"]["failed_small_response_count"], 6)
        self.assertFalse(result["decision"]["binary_labeling_allowed"])


if __name__ == "__main__":
    unittest.main()
