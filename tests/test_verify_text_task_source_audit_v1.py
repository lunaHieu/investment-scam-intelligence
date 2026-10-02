import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "verify_text_task_source_audit_v1.py"
REGISTRY_PATH = REPO_ROOT / "registry" / "analyses" / "text_task_source_audit_v1.json"
SPEC = importlib.util.spec_from_file_location("verify_text_task_source_audit_v1", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class VerifyTextTaskSourceAuditV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = MODULE.verify(REGISTRY_PATH)

    def test_hash_pinned_audit_reproduces(self):
        self.assertTrue(self.result["valid"], self.result["errors"])
        self.assertEqual(self.result["source_role_count"], 6)
        self.assertGreaterEqual(self.result["checked_artifact_count"], 17)

    def test_no_model_or_partition_gate_opened(self):
        self.assertEqual(self.result["model_fit_operations"], 0)
        self.assertEqual(self.result["validation_or_test_openings"], 0)


if __name__ == "__main__":
    unittest.main()

