import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]


class ReadyChannelCurrentStageRegistriesV1Tests(unittest.TestCase):
    def test_current_stage_registries_pin_all_inputs(self) -> None:
        for name in (
            "target_text_corpus_v1_ready_channel_cdx_bulk_result_v1.json",
            "target_text_corpus_v1_ready_channel_capture_plan_v1.json",
            "current_test_suite_lifecycle_v3.json",
        ):
            value = json.loads((ROOT / "registry" / "analyses" / name).read_text(encoding="utf-8"))
            for item in value.get("inputs", []) + value.get("implementation", []) + value.get("consumed_outputs", []):
                path = Path(item["path"])
                if not path.is_absolute():
                    path = ROOT / path
                self.assertTrue(path.is_file(), item["path"])
                self.assertEqual(sha256_file(path), item["sha256"], item["path"])

    def test_capture_and_research_gates_remain_closed(self) -> None:
        plan = json.loads((ROOT / "registry" / "analyses" / "target_text_corpus_v1_ready_channel_capture_plan_v1.json").read_text(encoding="utf-8"))
        self.assertEqual(plan["findings"]["planned_capture_rows"], 53)
        self.assertEqual(plan["findings"]["valid_empty_metadata_rows"], 16)
        self.assertFalse(plan["decision"]["capture_execution_authorized"])
        self.assertFalse(plan["decision"]["labeling_allowed"])


if __name__ == "__main__":
    unittest.main()
