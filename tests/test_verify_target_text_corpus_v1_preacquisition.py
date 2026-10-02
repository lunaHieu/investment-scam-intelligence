import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "verify_target_text_corpus_v1_preacquisition.py"
REGISTRY_PATH = (
    REPO_ROOT / "registry" / "analyses" / "target_text_corpus_v1_preacquisition.json"
)
SPEC = importlib.util.spec_from_file_location(
    "verify_target_text_corpus_v1_preacquisition", SCRIPT_PATH
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class VerifyTargetTextCorpusV1PreacquisitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = MODULE.verify(REGISTRY_PATH)

    def test_hash_pinned_artifacts_verify(self):
        self.assertTrue(self.result["valid"], self.result["errors"])
        self.assertGreaterEqual(self.result["checked_artifact_count"], 11)
        self.assertEqual(self.result["opened_record_count"], 107)

    def test_capture_and_model_gates_remain_closed(self):
        self.assertFalse(self.result["channel_gate_passed"])
        self.assertFalse(self.result["capture_allowed"])
        self.assertEqual(self.result["model_fit_operations"], 0)
        self.assertEqual(self.result["legacy_case_id_gap_count"], 86)


if __name__ == "__main__":
    unittest.main()
