import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "verify_mendeley_text_challenger_v4.py"
REGISTRY_PATH = REPO_ROOT / "registry" / "models" / "mendeley_text_challenger_v4.json"
SPEC = importlib.util.spec_from_file_location("verify_semantic_v4_registry", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class VerifySemanticChallengerV4RegistryTests(unittest.TestCase):
    def test_registry_and_all_outputs_are_frozen_and_valid(self):
        report = MODULE.verify(REGISTRY_PATH)
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["checked_artifact_count"], 16)
        self.assertFalse(report["development_verification"]["validation_opened"])


if __name__ == "__main__":
    unittest.main()
