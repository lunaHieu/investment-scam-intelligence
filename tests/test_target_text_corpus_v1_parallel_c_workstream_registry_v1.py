import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "target_text_corpus_v1_parallel_c_workstream_v1.json"


class ParallelCWorkstreamRegistryV1Tests(unittest.TestCase):
    def test_registry_pins_c1_and_preserves_external_and_model_gates(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"] + data["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item)
            self.assertEqual(sha256_file(path), item["sha256"], item)
        result = data["result"]
        self.assertEqual(result["scope_items"], 5)
        self.assertEqual(result["required_groups"], 300)
        self.assertEqual(result["admitted_groups"], 0)
        self.assertEqual(result["conditional_residual_gap"], 258)
        self.assertEqual(result["lawful_external_artifacts_acquired"], 0)
        self.assertTrue(data["decision"]["c1_complete"])
        self.assertFalse(data["decision"]["network_execution_allowed"])
        self.assertFalse(data["decision"]["candidate_enumeration_allowed"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
