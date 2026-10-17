import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "registry" / "analyses" / "data_sufficiency_audit_v2.json"


class DataSufficiencyAuditV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = json.loads(AUDIT.read_text(encoding="utf-8"))

    def test_all_pinned_inputs_and_implementation_are_current(self) -> None:
        for item in self.data["inputs"] + self.data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])

    def test_v1_denominators_are_preserved(self) -> None:
        prior = json.loads(
            (ROOT / "registry/analyses/data_sufficiency_audit_v1.json").read_text(encoding="utf-8")
        )["findings"]
        current = self.data["findings"]
        self.assertEqual(current["raw_storage"], prior["raw_storage"])
        self.assertEqual(current["historical_benchmark"], prior["historical_benchmark"])
        self.assertEqual(current["reference_metadata"], prior["reference_metadata"])
        self.assertEqual(current["fresh_target_corpus"], prior["fresh_target_corpus"])
        self.assertEqual(current["fresh_target_corpus"]["validated_release_groups"], 0)
        self.assertEqual(current["fresh_target_corpus"]["required_groups"], 300)

    def test_sec_progress_recomputes_from_current_ledger(self) -> None:
        ledger = json.loads(
            (ROOT / "registry/analyses/project_state_gap_ledger_v6.json").read_text(encoding="utf-8")
        )["state_amendments"]["P1_SEC_IAPD"]
        pipeline = self.data["findings"]["acquisition_pipeline"]
        self.assertEqual(pipeline["sec_iapd_candidates"], ledger["planned"])
        self.assertEqual(pipeline["sec_iapd_resolved"], ledger["resolved"])
        self.assertEqual(pipeline["sec_iapd_available"], ledger["available"])
        self.assertEqual(pipeline["sec_iapd_unavailable"], ledger["unavailable"])
        self.assertEqual(pipeline["sec_iapd_unresolved"], ledger["unresolved"])
        self.assertEqual(pipeline["sec_iapd_resolution_percent"], 93.04)
        self.assertEqual(pipeline["sec_iapd_captured_raw_artifacts"], 0)
        self.assertEqual(pipeline["sec_iapd_training_ready_rows"], 0)
        self.assertFalse(pipeline["capture_plan_open"])

    def test_readiness_and_model_gates_remain_closed(self) -> None:
        decision = self.data["decision"]
        self.assertTrue(decision["existing_raw_integrity_complete"])
        self.assertFalse(decision["total_planned_raw_acquisition_complete"])
        self.assertTrue(decision["baseline_internal_training_data_exists"])
        self.assertFalse(decision["fresh_target_training_ready"])
        self.assertFalse(decision["model_promotion_allowed"])
        self.assertFalse(decision["validation_or_test_opening_allowed"])
        self.assertFalse(decision["candidate_or_reference_counts_are_training_rows"])
        self.assertFalse(self.data["safety_contract"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
