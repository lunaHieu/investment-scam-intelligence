import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "verify_target_text_corpus_v1_channel_terms.py"
PROTOCOL_PATH = REPO_ROOT / "configs" / "target_text_corpus_v1_channel_terms_v1.json"
REGISTRY_PATH = REPO_ROOT / "registry" / "analyses" / "target_text_corpus_v1_channel_terms_v1.json"
SPEC = importlib.util.spec_from_file_location("verify_channel_terms", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class TargetTextCorpusV1ChannelTermsTests(unittest.TestCase):
    def test_protocol_and_source_addendum_validate(self):
        result = MODULE.validate_protocol(PROTOCOL_PATH)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["source_count"], 2)
        self.assertEqual(result["replacement_channel_count"], 2)
        self.assertEqual(
            result["registered_channels_by_target_status"],
            {"CONFIRMED": 2, "LEGITIMATE": 2},
        )

    def test_acquisition_and_model_gates_remain_closed(self):
        result = MODULE.validate_protocol(PROTOCOL_PATH)
        self.assertTrue(result["channel_protocol_registration_gate_passed"])
        self.assertFalse(result["candidate_enumeration_allowed"])
        self.assertFalse(result["candidate_capture_allowed"])
        self.assertEqual(result["model_fit_operations"], 0)

    def test_registry_verifies(self):
        result = MODULE.verify_registry(REGISTRY_PATH)
        self.assertTrue(result["valid"], result["errors"])
        self.assertTrue(result["channel_protocol_registration_gate_passed"])
        self.assertFalse(result["candidate_capture_allowed"])


if __name__ == "__main__":
    unittest.main()
