import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "reproducibility_current_state_v16.json"


class ReproducibilityCurrentStateV16Tests(unittest.TestCase):
    def test_current_navigation_registers_a4_without_opening_models(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "CURRENT_A4_REPAIR_PROTOCOL_A1_A2_UNCHANGED")
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item)
            self.assertEqual(sha256_file(path), item["sha256"], item)
        state = data["current_state"]
        self.assertEqual(state["owner_accepted_repair_population"], 42)
        self.assertEqual(state["admission_fields_credited_now"], 0)
        self.assertEqual(state["fresh_v1_core_admitted_groups"], 0)
        self.assertFalse(state["a1_cdx_network_executed"])
        self.assertFalse(state["a2_v11_network_executed"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
