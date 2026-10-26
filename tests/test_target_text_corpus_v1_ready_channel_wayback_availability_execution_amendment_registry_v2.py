import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry/analyses/target_text_corpus_v1_ready_channel_wayback_availability_execution_amendment_v2.json"


class ReadyChannelAvailabilityExecutionAmendmentRegistryV2Tests(unittest.TestCase):
    def test_hashes_and_gate_decision(self) -> None:
        value = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertTrue(value["result"]["gate_open"])
        self.assertFalse(value["result"]["a1_rate_limit"])
        self.assertTrue(value["decision"]["b5_execution_allowed_now"])
        self.assertFalse(value["decision"]["universal_fixed_24h_retry_chain_allowed"])
        for item in value["inputs"] + value["implementation"] + value["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertEqual(sha256_file(path), item["sha256"])


if __name__ == "__main__":
    unittest.main()
