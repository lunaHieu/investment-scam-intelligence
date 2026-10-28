import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_target_text_corpus_v1_ready_channel_capture_plan_v1 import build
from scripts.verify_target_text_corpus_v1_ready_channel_capture_plan_v1 import verify


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "target_text_corpus_v1_ready_channel_capture_plan_release_v1.json"


class ReadyChannelCapturePlanV1Tests(unittest.TestCase):
    def test_real_release_builds_exact_53_without_network_or_capture(self) -> None:
        plan = build(RELEASE)
        self.assertEqual(plan["resolved_metadata_rows"], 69)
        self.assertEqual(plan["planned_capture_count"], 53)
        self.assertEqual(plan["no_eligible_snapshot_count"], 16)
        self.assertEqual(plan["planned_by_cohort"], {"DEVELOPMENT": 37, "EXTERNAL_HOLDOUT": 16})
        self.assertEqual(plan["results"][0]["availability_plan_id"], "TTCV1_B3_AVAIL_002")
        self.assertEqual(plan["results"][-1]["availability_plan_id"], "TTCV1_B3_AVAIL_070")
        self.assertFalse(plan["decision"]["capture_execution_authorized"])
        self.assertEqual(plan["safety_contract"]["network_operations"], 0)

    def test_independent_verifier_recomputes_exact_plan(self) -> None:
        plan = build(RELEASE)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
            result = verify(RELEASE, path)
        self.assertEqual(result["status"], "PASS_EXACT_53_ELIGIBLE_CAPTURE_PLAN_SEPARATE_RELEASE_MAY_BE_PREPARED", result["errors"])
        self.assertFalse(result["decision"]["capture_execution_authorized"])


if __name__ == "__main__":
    unittest.main()
