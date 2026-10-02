import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = REPO_ROOT / "configs" / "target_text_corpus_v1_protocol.json"


class TargetTextCorpusV1ProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))

    def test_target_is_case_level_and_uncertain_is_excluded(self):
        target = self.protocol["target_task"]
        self.assertEqual(target["prediction_unit"], "ARTIFACT_WITH_CASE_LEVEL_GROUND_TRUTH")
        self.assertEqual(target["positive_target"]["required_case_status"], "CONFIRMED")
        self.assertEqual(target["negative_target"]["required_case_status"], "LEGITIMATE")
        self.assertIn("excluded from binary fitting", target["uncertain_policy"])

    def test_historical_and_opened_data_cannot_enter_new_training(self):
        roles = self.protocol["source_role_contract"]
        self.assertEqual(roles["mendeley_v2"]["rows_allowed_in_new_target_corpus"], 0)
        self.assertEqual(
            roles["opened_external_cohorts"]["rows_allowed_in_training_or_model_selection"],
            0,
        )

    def test_data_gates_are_balanced_and_holdout_is_separate(self):
        gates = self.protocol["minimum_data_gates"]
        self.assertEqual(gates["schema_and_review_pilot"]["minimum_confirmed_groups"], 20)
        self.assertEqual(gates["schema_and_review_pilot"]["minimum_legitimate_groups"], 20)
        self.assertFalse(gates["schema_and_review_pilot"]["model_training_allowed"])
        self.assertEqual(gates["development_corpus"]["minimum_total_groups"], 240)
        self.assertEqual(gates["untouched_external_holdout"]["minimum_total_groups"], 60)
        self.assertTrue(
            gates["untouched_external_holdout"]["must_use_separate_acquisition_wave"]
        )

    def test_current_gate_is_closed(self):
        safety = self.protocol["safety_contract"]
        self.assertEqual(safety["new_records_acquired"], 0)
        self.assertEqual(safety["model_fit_operations"], 0)
        self.assertEqual(safety["validation_or_test_openings"], 0)
        self.assertFalse(safety["training_allowed"])
        self.assertFalse(safety["deployment_allowed"])


if __name__ == "__main__":
    unittest.main()

