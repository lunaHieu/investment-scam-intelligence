import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_ready_channel_capture_continuation_release_v2 import sha


ROOT = Path(__file__).resolve().parents[1]


class ContinuationRegistriesV2Tests(unittest.TestCase):
    def test_registries_pin_all_inputs(self):
        names = (
            "target_text_corpus_v1_ready_channel_capture_continuation_result_v1.json",
            "target_text_corpus_v1_ready_channel_capture_continuation_plan_v2.json",
            "target_text_corpus_v1_ready_channel_capture_continuation_release_v2.json",
            "target_text_corpus_v1_ready_channel_row010_diagnostic_protocol_v1.json",
            "reproducibility_current_state_v44.json",
            "project_state_gap_ledger_v47.json",
        )
        for name in names:
            value = json.loads((ROOT / "registry" / "analyses" / name).read_text(encoding="utf-8"))
            for item in value.get("inputs", []) + value.get("implementation", []):
                path = Path(item["path"])
                path = path if path.is_absolute() else ROOT / path
                self.assertEqual(sha(path), item["sha256"], f"{name}: {item['path']}")

    def test_v2_policy_is_flexible_only_for_row_local_content_errors(self):
        value = json.loads(
            (ROOT / "registry" / "analyses" / "target_text_corpus_v1_ready_channel_capture_continuation_release_v2.json").read_text(encoding="utf-8")
        )
        self.assertTrue(value["findings"]["continue_on_row_local_content_error"])
        self.assertTrue(value["findings"]["stop_on_provider_or_transport_error"])


if __name__ == "__main__":
    unittest.main()
