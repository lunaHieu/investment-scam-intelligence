import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "reproducibility_current_state_v2.json"


class ReproducibilityCurrentStateV2Tests(unittest.TestCase):
    def test_guide_inputs_and_implementation_are_hash_bound(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"] + [data["output"]]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])
        self.assertTrue(all(data["coverage"].values()))
        self.assertEqual(data["current_entrypoint"], "registry/analyses/project_state_gap_ledger_v3.json")
        self.assertTrue(data["decision"]["module_compatible_external_verifier_documented"])
        self.assertTrue(data["decision"]["manual_packet_documented"])
        self.assertFalse(data["decision"]["training_allowed"])
        self.assertFalse(data["decision"]["validation_or_test_opening_allowed"])
        self.assertFalse(data["decision"]["network_execution_allowed_now"])


if __name__ == "__main__":
    unittest.main()
