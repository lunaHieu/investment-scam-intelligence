import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_ready_channel_capture_release_v1 import load, sha256_file


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "target_text_corpus_v1_ready_channel_capture_release_v1.json"
REPORT = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\ready_channel_wayback_capture_result_v1\capture_report_v1.json")
QA = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\ready_channel_wayback_capture_result_v1\independent_result_qa_v1.json")
PLAN = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\ready_channel_wayback_capture_plan_v1\capture_plan_v1.json")
PLAN_QA = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\ready_channel_wayback_capture_plan_v1\independent_plan_qa_v1.json")


class CurrentArtifactLifecycleV4Tests(unittest.TestCase):
    def test_consumed_capture_release_and_partial_result_verify(self) -> None:
        release = load(RELEASE)
        self.assertEqual(sha256_file(RELEASE), "2395a9af60c947426303650126159b4ead6994837259659f34f7b6e952e8451b")
        self.assertEqual(release["status"], "FROZEN_EXACT_53_ARCHIVE_ONLY_CAPTURE_SEPARATE_INVOCATION")
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        qa = json.loads(QA.read_text(encoding="utf-8"))
        self.assertEqual(sha256_file(REPORT), "6fffae3f13ebf60dc3733f10d89ada18a56b4c8d455858add8448857bb9df676")
        self.assertEqual(sha256_file(QA), "ecdd704723d9ca1af90eb5e3179c643ac5aad771bbd5178e3324e423d540d5b4")
        self.assertEqual(report["captured_count"], 3)
        self.assertEqual(report["failed_count"], 1)
        self.assertEqual(report["not_attempted_count"], 49)
        self.assertEqual(qa["status"], "PASS_PARTIAL_CAPTURE_PRESERVED_RETRY_RELEASE_REQUIRED")
        self.assertFalse(qa["decision"]["exact_text_release_may_be_prepared"])

    def test_consumed_capture_plan_membership_and_hash(self) -> None:
        plan = load(PLAN)
        self.assertEqual(sha256_file(PLAN), "824b1bbad2f0d396e31128ba62a62588ee6192453a4c213e803c2a5e7fd54ddd")
        self.assertEqual(plan["planned_capture_count"], 53)
        self.assertEqual(plan["planned_by_cohort"], {"DEVELOPMENT": 37, "EXTERNAL_HOLDOUT": 16})
        self.assertEqual(len(plan["results"]), 53)

    def test_capture_plan_qa_remains_pinned(self) -> None:
        qa = load(PLAN_QA)
        self.assertEqual(sha256_file(PLAN_QA), "50377c81d4a95ac257bd55f57d2da5f17bd8cc80e35e7eea1615b987991f2078")
        self.assertEqual(qa["status"], "PASS_EXACT_53_ELIGIBLE_CAPTURE_PLAN_SEPARATE_RELEASE_MAY_BE_PREPARED")
        self.assertFalse(qa["decision"]["capture_execution_authorized"])

    def test_executor_tooling_hash_remains_pinned_after_consumption(self) -> None:
        release = load(RELEASE)
        executor = next(item for item in release["tooling"] if item["role"] == "executor")
        self.assertEqual(sha256_file(ROOT / executor["path"]), executor["sha256"])


if __name__ == "__main__":
    unittest.main()
