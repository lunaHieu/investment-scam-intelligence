import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "verify_target_text_corpus_v1_protocol.py"
REGISTRY_PATH = REPO_ROOT / "registry" / "analyses" / "target_text_corpus_v1_protocol.json"
SPEC = importlib.util.spec_from_file_location("verify_target_text_corpus_v1_protocol", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class VerifyTargetTextCorpusV1ProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = MODULE.verify(REGISTRY_PATH)

    def test_hash_pinned_protocol_reproduces(self):
        self.assertTrue(self.result["valid"], self.result["errors"])
        self.assertEqual(self.result["protocol_dependency_count"], 11)
        self.assertGreaterEqual(self.result["checked_artifact_count"], 15)

    def test_data_and_model_gates_remain_closed(self):
        self.assertEqual(self.result["new_records_acquired"], 0)
        self.assertEqual(self.result["model_fit_operations"], 0)
        self.assertEqual(self.result["validation_or_test_openings"], 0)


if __name__ == "__main__":
    unittest.main()
