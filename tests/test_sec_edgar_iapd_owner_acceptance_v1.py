import json
import tempfile
import unittest
from pathlib import Path

from scripts.materialize_sec_edgar_iapd_owner_acceptance_v1 import build
from scripts.reconcile_sec_edgar_iapd_reviews_v1 import build as reconcile
from scripts.verify_sec_edgar_iapd_owner_acceptance_v1 import verify
from scripts.verify_sec_edgar_iapd_reconciliation_v1 import verify as verify_reconciliation
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file
from tests import test_sec_edgar_iapd_reconciliation_v1 as reconciliation_helpers


class SecEdgarIapdOwnerAcceptanceV1Tests(unittest.TestCase):
    def make_inputs(self, directory: Path, disagree: bool = False) -> tuple[Path, Path, Path]:
        helper = reconciliation_helpers.SecEdgarIapdReconciliationV1Tests()
        reconciliation = reconcile(*helper.make_reviews(directory, disagree=disagree))
        reconciliation_path = directory / "reconciliation.json"
        reconciliation_path.write_text(json.dumps(reconciliation, indent=2) + "\n", encoding="utf-8")
        reconciliation_qa = verify_reconciliation(reconciliation_path)
        self.assertEqual(reconciliation_qa["status"], "PASS_RECONCILIATION_REPRODUCED_OWNER_ACCEPTANCE_REQUIRED")
        reconciliation_qa_path = directory / "reconciliation_qa.json"
        reconciliation_qa_path.write_text(json.dumps(reconciliation_qa, indent=2) + "\n", encoding="utf-8")
        acceptance = {
            "acceptance_id": "ISI_SEC_EDGAR_IAPD_OWNER_ACCEPTANCE_V1",
            "reconciliation_sha256": sha256_file(reconciliation_path),
            "owner_attestation": {"reviewed_reconciliation": True, "explicit_acceptance": True},
            "records": [
                {
                    "record_id": row["record_id"],
                    "accepted": row["reconciled_recommendation"] == "LEGITIMATE",
                    "rationale": "The reconciled evidence and both independent reviews were inspected; this explicit decision preserves every frozen safety gate.",
                }
                for row in reconciliation["records"]
            ],
        }
        acceptance_path = directory / "owner_acceptance.json"
        acceptance_path.write_text(json.dumps(acceptance, indent=2) + "\n", encoding="utf-8")
        return reconciliation_path, reconciliation_qa_path, acceptance_path

    def test_explicit_acceptance_materializes_label_but_not_training_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            inputs = self.make_inputs(directory)
            result = build(*inputs)
            self.assertEqual(result["summary"]["accepted_records"], 1)
            self.assertEqual(result["summary"]["training_eligible_records"], 0)
            self.assertEqual(result["records"][0]["cohort"], "DEVELOPMENT")
            self.assertEqual(result["records"][0]["training_eligible"], "NO_PENDING_BALANCED_DATASET_RELEASE")
            materialization_path = directory / "materialization.json"
            materialization_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            qa = verify(materialization_path, *inputs)
            self.assertEqual(qa["status"], "PASS_OWNER_ACCEPTANCE_MATERIALIZED_BALANCED_DATASET_RELEASE_REQUIRED")
            self.assertFalse(qa["decision"]["training_allowed_now"])

    def test_acceptance_cannot_redefine_frozen_cohort(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = self.make_inputs(Path(tmp))
            acceptance = json.loads(inputs[2].read_text(encoding="utf-8"))
            acceptance["records"][0]["cohort"] = "EXTERNAL_HOLDOUT"
            inputs[2].write_text(json.dumps(acceptance, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must not redefine cohort"):
                build(*inputs)

    def test_uncertain_reconciliation_cannot_be_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = self.make_inputs(Path(tmp), disagree=True)
            acceptance = json.loads(inputs[2].read_text(encoding="utf-8"))
            acceptance["records"][0]["accepted"] = True
            inputs[2].write_text(json.dumps(acceptance, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Cannot accept a non-LEGITIMATE"):
                build(*inputs)


if __name__ == "__main__":
    unittest.main()
