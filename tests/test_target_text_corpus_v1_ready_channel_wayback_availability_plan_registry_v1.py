import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "target_text_corpus_v1_ready_channel_wayback_availability_plan_v1.json"


class ReadyChannelWaybackAvailabilityPlanRegistryV1Tests(unittest.TestCase):
    def test_registry_pins_exact_70_plan_and_keeps_execution_closed(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"] + data["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item)
            self.assertEqual(sha256_file(path), item["sha256"], item)
        result = data["result"]
        self.assertEqual(result["plan_records"], 70)
        self.assertEqual(result["development_records"], 50)
        self.assertEqual(result["external_holdout_records"], 20)
        self.assertEqual(result["unique_hosts"], 70)
        self.assertEqual(result["unique_normalized_entities"], 70)
        self.assertEqual(result["development_holdout_host_overlap"], 0)
        self.assertEqual(result["development_holdout_entity_overlap"], 0)
        self.assertTrue(result["candidate_order_preserved"])
        self.assertTrue(result["planned_request_urls_round_trip"])
        self.assertEqual(result["future_minimum_delay_seconds"], 60.0)
        decision = data["decision"]
        self.assertTrue(decision["b4_crash_safe_execution_release_preparation_allowed"])
        self.assertFalse(decision["network_execution_allowed"])
        self.assertFalse(decision["wayback_query_execution_allowed"])
        self.assertFalse(decision["artifact_capture_allowed"])
        self.assertFalse(decision["training_allowed"])


if __name__ == "__main__":
    unittest.main()
