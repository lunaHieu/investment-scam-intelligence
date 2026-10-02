import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "synthesize_text_task_source_audit_v1.py"
SPEC = importlib.util.spec_from_file_location("text_task_source_audit_v1", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class TextTaskSourceAuditV1Tests(unittest.TestCase):
    def test_protocol_and_inputs_are_hash_pinned(self):
        protocol, inputs = MODULE.verify_protocol()
        self.assertEqual(protocol["status"], "LOCKED_BEFORE_NEW_SYNTHESIS_NO_NEW_DATA")
        self.assertEqual(len(inputs), 12)

    def test_source_roles_do_not_create_final_ground_truth(self):
        roles = MODULE.source_role_recommendations()
        self.assertEqual(len(roles), 6)
        self.assertTrue(
            all(not item["use_as_final_target_domain_ground_truth"] for item in roles.values())
        )
        self.assertEqual(
            roles["twitter_bot_detection"]["recommended_role"],
            "ACCOUNT_OR_BEHAVIOR_AUXILIARY_TASK",
        )
        self.assertEqual(
            roles["conflicting_phishing_component"]["recommended_role"],
            "QUARANTINE",
        )

    def test_synthesis_preserves_closed_model_and_data_gates(self):
        protocol, inputs = MODULE.verify_protocol()
        result = MODULE.build_result(protocol, inputs)
        self.assertTrue(result["decision"]["primary_task_misalignment_found"])
        self.assertFalse(result["decision"]["train_another_model_now"])
        self.assertFalse(result["decision"]["new_model_or_corpus_configuration_authorized"])
        self.assertEqual(result["safety_contract"]["model_fit_operations"], 0)
        self.assertEqual(result["safety_contract"]["validation_or_test_openings"], 0)


if __name__ == "__main__":
    unittest.main()

