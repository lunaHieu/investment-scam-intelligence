import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    REPO_ROOT
    / "scripts"
    / "verify_mendeley_text_challenger_v4_oof_error_analysis_registry.py"
)
REGISTRY_PATH = (
    REPO_ROOT
    / "registry"
    / "analyses"
    / "mendeley_text_challenger_v4_oof_error_analysis.json"
)
SPEC = importlib.util.spec_from_file_location("verify_semantic_v4_error_registry", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class VerifySemanticChallengerV4OOFErrorRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = MODULE.verify(REGISTRY_PATH)

    def test_registry_and_report_are_hash_pinned_and_reproducible(self):
        self.assertTrue(self.result["valid"], self.result["errors"])
        self.assertTrue(self.result["report_valid"])
        self.assertGreaterEqual(self.result["checked_artifact_count"], 10)

    def test_registry_preserves_closed_data_and_model_gates(self):
        self.assertFalse(self.result["validation_opened"])
        self.assertEqual(self.result["model_fit_operations"], 0)


if __name__ == "__main__":
    unittest.main()

