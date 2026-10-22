import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "target_text_corpus_v1_acquisition_wave_plan_v2.json"


class AcquisitionWavePlanRegistryV2Tests(unittest.TestCase):
    def test_registry_pins_plan_qa_and_closed_network(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"] + data["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["role"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["role"])
        self.assertEqual(data["result"]["development_residual_target"], 207)
        self.assertEqual(data["result"]["external_holdout_residual_target"], 51)
        self.assertFalse(data["decision"]["network_allowed_now"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
