import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    REPO_ROOT / "scripts" / "verify_target_text_corpus_v1_legacy_group_remediation.py"
)
PROTOCOL_PATH = (
    REPO_ROOT / "configs" / "target_text_corpus_v1_legacy_group_remediation_v1.json"
)
REGISTRY_PATH = (
    REPO_ROOT
    / "registry"
    / "analyses"
    / "target_text_corpus_v1_legacy_group_remediation_v1.json"
)
SPEC = importlib.util.spec_from_file_location("verify_legacy_group_remediation", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class VerifyLegacyGroupRemediationTests(unittest.TestCase):
    def test_independent_review_recomputes_every_legacy_record(self):
        result = MODULE.independent_review(PROTOCOL_PATH)
        self.assertTrue(result["valid"], result["errors"])
        self.assertFalse(result["builder_module_imported"])
        self.assertEqual(result["legacy_records_compared"], 86)
        self.assertEqual(result["queue_joins_recomputed"], 86)
        self.assertEqual(result["components_recomputed"], 94)
        self.assertEqual(result["anchored_legacy_records"], 13)
        self.assertEqual(result["unanchored_exclusion_only_records"], 73)

    def test_registry_verifier_keeps_capture_gate_closed(self):
        result = MODULE.verify_registry(REGISTRY_PATH)
        self.assertTrue(result["valid"], result["errors"])
        self.assertTrue(result["independent_review_passed"])
        self.assertFalse(result["capture_allowed"])
        self.assertEqual(result["model_fit_operations"], 0)


if __name__ == "__main__":
    unittest.main()
