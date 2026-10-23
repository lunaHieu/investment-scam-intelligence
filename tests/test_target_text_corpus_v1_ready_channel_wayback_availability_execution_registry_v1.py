import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "target_text_corpus_v1_ready_channel_wayback_availability_execution_v1.json"


class ReadyChannelWaybackAvailabilityExecutionRegistryV1Tests(unittest.TestCase):
    def test_registry_pins_b4_and_keeps_network_capture_and_models_closed(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"] + data["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item)
            self.assertEqual(sha256_file(path), item["sha256"], item)
        result = data["result"]
        self.assertEqual(result["plan_records"], 70)
        self.assertEqual(result["minimum_delay_seconds"], 60.0)
        self.assertEqual(result["maximum_attempts_per_candidate"], 1)
        self.assertEqual(result["minimum_cooldown_seconds_after_a1"], 86400)
        self.assertTrue(result["dynamic_a1_report_cooldown_required"])
        self.assertTrue(result["partial_journal_reserved_before_network"])
        self.assertFalse(result["partial_journal_auto_resume_allowed"])
        self.assertEqual(result["network_requests_executed"], 0)
        decision = data["decision"]
        self.assertTrue(decision["b5_execution_may_run_only_after_dynamic_gate"])
        self.assertFalse(decision["network_execution_allowed_now"])
        self.assertFalse(decision["artifact_capture_allowed"])
        self.assertFalse(decision["training_allowed"])


if __name__ == "__main__":
    unittest.main()
