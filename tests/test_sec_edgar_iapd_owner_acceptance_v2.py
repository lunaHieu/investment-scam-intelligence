import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_sec_edgar_iapd_owner_acceptance_packet_v2 import build as build_packet
from scripts.materialize_sec_edgar_iapd_owner_acceptance_v2 import build as materialize
from scripts.record_sec_edgar_iapd_owner_acceptance_v2 import build as record_acceptance
from scripts.verify_sec_edgar_iapd_owner_acceptance_v2 import verify
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


class SecEdgarIapdOwnerAcceptanceV2Tests(unittest.TestCase):
    def make_inputs(self, directory: Path) -> tuple[Path, Path, Path, Path]:
        records = []
        for index in range(42):
            cohort = "DEVELOPMENT" if index < 33 else "EXTERNAL_HOLDOUT"
            records.append({
                "record_id": f"LEGIT_{index:02d}",
                "cohort": cohort,
                "review_agreement": True,
                "reconciled_recommendation": "LEGITIMATE",
                "owner_acceptance": "PENDING",
                "ground_truth_status": "UNCERTAIN",
                "label_created": False,
                "training_eligible": "NO",
            })
        for index in range(14):
            cohort = "DEVELOPMENT" if index < 11 else "EXTERNAL_HOLDOUT"
            records.append({
                "record_id": f"UNCERTAIN_{index:02d}",
                "cohort": cohort,
                "review_agreement": index >= 7,
                "reconciled_recommendation": "UNCERTAIN",
                "owner_acceptance": "PENDING",
                "ground_truth_status": "UNCERTAIN",
                "label_created": False,
                "training_eligible": "NO",
            })
        reconciliation = {
            "reconciliation_id": "ISI_SEC_EDGAR_IAPD_RECONCILIATION_V2",
            "status": "RECONCILED_RECOMMENDATIONS_COMPLETE_OWNER_ACCEPTANCE_REQUIRED",
            "records": records,
        }
        reconciliation_path = directory / "reconciliation.json"
        reconciliation_path.write_text(json.dumps(reconciliation, indent=2) + "\n", encoding="utf-8")
        qa = {
            "status": "PASS_CAPTURED_SUBSET_RECONCILIATION_REPRODUCED_OWNER_ACCEPTANCE_REQUIRED",
            "inputs": {"reconciliation_sha256": sha256_file(reconciliation_path)},
            "decision": {"owner_acceptance_required": True},
        }
        qa_path = directory / "reconciliation_qa.json"
        qa_path.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
        packet_path = directory / "pending_packet.json"
        packet_path.write_text(json.dumps(build_packet(reconciliation_path, qa_path), indent=2) + "\n", encoding="utf-8")
        authorization = {
            "authorization_id": "ISI_SEC_EDGAR_IAPD_OWNER_AUTHORIZATION_V2",
            "accepted_at": "2026-10-22T15:36:14+07:00",
            "adopter_role": "PROJECT_OWNER",
            "authorization_source": "The project owner reviewed the frozen reconciliation report and explicitly authorized its conservative materialization.",
            "status": "FROZEN_OWNER_AUTHORIZATION",
            "reconciliation_sha256": sha256_file(reconciliation_path),
            "reconciliation_qa_sha256": sha256_file(qa_path),
            "scope": {"expected_records": 56, "expected_recommendations": {"LEGITIMATE": 42, "UNCERTAIN": 14}},
            "owner_attestation": {"reviewed_reconciliation_snapshot": True, "explicit_acceptance": True, "independent_evidence_rereview_claimed": False},
            "decision_policy": {"accept_all_reconciled_legitimate": True, "retain_all_uncertain_without_label": True, "external_holdout_training_allowed": False, "training_allowed_now": False},
        }
        authorization_path = directory / "authorization.json"
        authorization_path.write_text(json.dumps(authorization, indent=2) + "\n", encoding="utf-8")
        return reconciliation_path, qa_path, packet_path, authorization_path

    def test_materializes_frozen_partition_without_opening_training(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            reconciliation, qa, packet, authorization = self.make_inputs(directory)
            acceptance = record_acceptance(packet, authorization)
            acceptance_path = directory / "acceptance.json"
            acceptance_path.write_text(json.dumps(acceptance, indent=2) + "\n", encoding="utf-8")
            result = materialize(reconciliation, qa, acceptance_path)
            self.assertEqual(result["summary"]["accepted_records"], 42)
            self.assertEqual(result["summary"]["uncertain_retained"], 14)
            self.assertEqual(result["summary"]["accepted_by_cohort"], {"DEVELOPMENT": 33, "EXTERNAL_HOLDOUT": 9})
            self.assertEqual(result["summary"]["training_eligible_records"], 0)
            materialization_path = directory / "materialization.json"
            materialization_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            verification = verify(materialization_path, reconciliation, qa, acceptance_path)
            self.assertEqual(verification["status"], "PASS_OWNER_ACCEPTANCE_42_LABELS_14_UNCERTAIN_BALANCED_DATASET_RELEASE_REQUIRED")
            self.assertFalse(verification["decision"]["training_allowed_now"])

    def test_authorization_must_bind_to_frozen_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = self.make_inputs(Path(tmp))
            authorization = json.loads(inputs[3].read_text(encoding="utf-8"))
            authorization["reconciliation_sha256"] = "0" * 64
            inputs[3].write_text(json.dumps(authorization, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not bound"):
                record_acceptance(inputs[2], inputs[3])

    def test_uncertain_record_cannot_be_promoted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            reconciliation, qa, packet, authorization = self.make_inputs(directory)
            acceptance = record_acceptance(packet, authorization)
            uncertain = next(row for row in acceptance["records"] if row["reconciled_recommendation"] == "UNCERTAIN")
            uncertain["accepted"] = True
            acceptance_path = directory / "acceptance.json"
            acceptance_path.write_text(json.dumps(acceptance, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Cannot accept a non-LEGITIMATE"):
                materialize(reconciliation, qa, acceptance_path)


if __name__ == "__main__":
    unittest.main()
