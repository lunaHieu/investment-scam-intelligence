import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "reproducibility_current_state_v1.json"


class ReproducibilityCurrentStateV1Tests(unittest.TestCase):
    def test_guide_and_inputs_are_hash_bound_with_closed_gates(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + [data["output"]]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])
        self.assertTrue(all(data["coverage"].values()))
        self.assertFalse(data["decision"]["conversation_history_is_authoritative_artifact"])
        self.assertFalse(data["decision"]["training_allowed"])
        self.assertFalse(data["decision"]["validation_or_test_opening_allowed"])
        self.assertFalse(data["decision"]["network_execution_allowed"])


if __name__ == "__main__":
    unittest.main()
