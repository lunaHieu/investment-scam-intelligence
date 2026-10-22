import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.analyze_target_text_corpus_v1_owner_accepted_admission_repair_v1 import analyze, validate_protocol
from scripts.verify_target_text_corpus_v1_owner_accepted_admission_repair_v1 import verify


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "target_text_corpus_v1_owner_accepted_admission_repair_protocol_v1.json"


class OwnerAcceptedAdmissionRepairV1Tests(unittest.TestCase):
    def test_real_population_is_exact_and_no_field_is_prematurely_credited(self) -> None:
        result = analyze(CONFIG)
        self.assertEqual(result["status"], "PASS_EXACT_42_READINESS_AUDITED_ZERO_FIELDS_PREMATURELY_CREDITED")
        self.assertEqual(result["population"]["record_count"], 42)
        self.assertEqual(result["population"]["development_count"], 33)
        self.assertEqual(result["population"]["external_holdout_count"], 9)
        self.assertEqual(result["decision"]["v1_core_admitted_records"], 0)
        self.assertFalse(result["decision"]["repaired_candidate_manifest_created"])
        self.assertFalse(result["decision"]["training_allowed"])
        self.assertTrue(all(section["admission_credit_now"] == 0 for section in result["blocker_disposition"].values()))

    def test_protocol_classifies_all_nine_blockers_exactly_once(self) -> None:
        config, _ = validate_protocol(CONFIG)
        blockers = config["blocker_contract"]
        classified = [
            item["audit_blocker"]
            for section in ("human_review_now", "offline_evidence_packet_now_but_no_admission_credit", "full_channel_or_population_only")
            for item in blockers[section]
        ]
        self.assertEqual(len(classified), 9)
        self.assertEqual(len(set(classified)), 9)
        self.assertEqual(set(classified), set(blockers["audit_blockers"]))

    def test_semantic_group_promotion_is_rejected(self) -> None:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        tampered = copy.deepcopy(config)
        tampered["evidence_reuse_contract"]["technical_group_may_be_renamed_as_semantic_group"] = True
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", dir=ROOT / "configs", encoding="utf-8", delete=False) as handle:
            json.dump(tampered, handle)
            path = Path(handle.name)
        try:
            with self.assertRaisesRegex(PermissionError, "semantic group"):
                validate_protocol(path)
        finally:
            path.unlink(missing_ok=True)

    def test_result_verifier_recomputes_full_report(self) -> None:
        report = analyze(CONFIG)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            qa = verify(CONFIG, path)
        self.assertEqual(qa["status"], "PASS_READINESS_REPORT_FULLY_RECOMPUTED")
        self.assertEqual(qa["checks"]["record_count"], 42)
        self.assertFalse(qa["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
