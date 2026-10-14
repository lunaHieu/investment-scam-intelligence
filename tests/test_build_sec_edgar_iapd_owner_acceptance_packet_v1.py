import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_sec_edgar_iapd_owner_acceptance_packet_v1 import build
from scripts.materialize_sec_edgar_iapd_owner_acceptance_v1 import build as materialize
from scripts.reconcile_sec_edgar_iapd_reviews_v1 import build as reconcile
from scripts.verify_sec_edgar_iapd_reconciliation_v1 import verify as verify_reconciliation
from tests import test_sec_edgar_iapd_reconciliation_v1 as reconciliation_helpers


class BuildSecEdgarIapdOwnerAcceptancePacketV1Tests(unittest.TestCase):
    def make_inputs(self, directory: Path) -> tuple[Path, Path]:
        helper = reconciliation_helpers.SecEdgarIapdReconciliationV1Tests()
        reconciliation = reconcile(*helper.make_reviews(directory))
        reconciliation_path = directory / "reconciliation.json"
        reconciliation_path.write_text(json.dumps(reconciliation, indent=2) + "\n", encoding="utf-8")
        qa = verify_reconciliation(reconciliation_path)
        reconciliation_qa_path = directory / "reconciliation_qa.json"
        reconciliation_qa_path.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
        return reconciliation_path, reconciliation_qa_path

    def test_builder_creates_pending_packet_without_preacceptance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = self.make_inputs(Path(tmp))
            packet = build(*inputs)
            self.assertEqual(packet["status"], "PENDING_OWNER_DECISIONS")
            self.assertFalse(packet["owner_attestation"]["reviewed_reconciliation"])
            self.assertIsNone(packet["records"][0]["accepted"])
            self.assertNotIn("cohort", packet["records"][0])

    def test_pending_packet_cannot_be_materialized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            inputs = self.make_inputs(directory)
            packet_path = directory / "acceptance.json"
            packet_path.write_text(json.dumps(build(*inputs), indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "decisions are not complete"):
                materialize(*inputs, packet_path)


if __name__ == "__main__":
    unittest.main()
