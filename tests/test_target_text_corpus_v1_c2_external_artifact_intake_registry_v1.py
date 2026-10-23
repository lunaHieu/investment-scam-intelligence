import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "target_text_corpus_v1_c2_external_artifact_intake_preflight_v1.json"


class C2ExternalArtifactIntakeRegistryV1Tests(unittest.TestCase):
    def test_registry_hashes_and_external_gate(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "C2_PREFLIGHT_COMPLETE_EXTERNAL_ARTIFACT_OR_RIGHTS_INPUT_PENDING")
        for section in ("inputs", "implementation", "outputs"):
            for item in data[section]:
                path = Path(item["path"])
                if not path.is_absolute():
                    path = ROOT / path
                self.assertTrue(path.is_file(), item["role"])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["role"])
        self.assertEqual(data["result"]["source_contracts"], 4)
        self.assertEqual(data["result"]["source_files_acquired"], 0)
        self.assertTrue(data["decision"]["c2_preflight_complete"])
        self.assertFalse(data["decision"]["c2_intake_complete"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
