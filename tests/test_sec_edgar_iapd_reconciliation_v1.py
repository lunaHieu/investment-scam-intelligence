import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_sec_edgar_iapd_blind_second_review_packet_v1 import build as build_blind
from scripts.reconcile_sec_edgar_iapd_reviews_v1 import build
from scripts.verify_sec_edgar_iapd_blind_second_review_v1 import verify as verify_second
from scripts.verify_sec_edgar_iapd_primary_review_v1 import verify as verify_primary
from scripts.verify_sec_edgar_iapd_reconciliation_v1 import verify
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file
from tests import test_sec_edgar_iapd_blind_second_review_v1 as second_helpers
from tests import test_sec_edgar_iapd_primary_review_v1 as primary_helpers


class SecEdgarIapdReconciliationV1Tests(unittest.TestCase):
    def make_reviews(self, directory: Path, disagree: bool = False) -> tuple[Path, Path, Path, Path]:
        primary_helper = primary_helpers.SecEdgarIapdPrimaryReviewV1Tests()
        primary_packet = primary_helper.make_packet(directory)
        primary = primary_helper.make_review(primary_packet)
        primary_path = directory / "primary_review.json"
        primary_path.write_text(json.dumps(primary, indent=2) + "\n", encoding="utf-8")
        primary_qa = verify_primary(primary_packet, primary_path)
        primary_qa_path = directory / "primary_review_qa.json"
        primary_qa_path.write_text(json.dumps(primary_qa, indent=2) + "\n", encoding="utf-8")
        blind = build_blind(primary_packet, primary_path, primary_qa_path)
        blind_path = directory / "blind_packet.json"
        blind_path.write_text(json.dumps(blind, indent=2) + "\n", encoding="utf-8")
        second_helper = second_helpers.SecEdgarIapdBlindSecondReviewV1Tests()
        second = second_helper.make_review(blind_path)
        if disagree:
            row = second["records"][0]
            row["second_recommendation"] = "UNCERTAIN"
            row["assessments"]["identity_linkage"] = "UNCERTAIN"
            row["uncertainty_reasons"] = ["The captured brand-to-registered-entity relationship is not explicit enough for an affirmative recommendation."]
        second_path = directory / "second_review.json"
        second_path.write_text(json.dumps(second, indent=2) + "\n", encoding="utf-8")
        second_qa = verify_second(blind_path, second_path)
        self.assertEqual(second_qa["status"], "PASS_BLIND_SECOND_REVIEW_RECONCILIATION_MAY_BE_PREPARED")
        second_qa_path = directory / "second_review_qa.json"
        second_qa_path.write_text(json.dumps(second_qa, indent=2) + "\n", encoding="utf-8")
        return primary_path, primary_qa_path, second_path, second_qa_path

    def test_agreement_creates_recommendation_but_not_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            paths = self.make_reviews(directory)
            result = build(*paths)
            reconciliation_path = directory / "reconciliation.json"
            reconciliation_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            self.assertEqual(result["summary"]["reconciled_recommendation_counts"], {"LEGITIMATE": 1})
            self.assertEqual(result["records"][0]["owner_acceptance"], "PENDING")
            self.assertFalse(result["records"][0]["label_created"])
            qa = verify(reconciliation_path)
            self.assertEqual(qa["status"], "PASS_RECONCILIATION_REPRODUCED_OWNER_ACCEPTANCE_REQUIRED")
            self.assertFalse(qa["decision"]["materialization_allowed_now"])

    def test_disagreement_is_forced_to_uncertain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.make_reviews(Path(tmp), disagree=True)
            result = build(*paths)
            row = result["records"][0]
            self.assertEqual(row["reconciled_recommendation"], "UNCERTAIN")
            self.assertEqual(row["reconciliation_rule"], "DISAGREEMENT_TO_UNCERTAIN")
            self.assertFalse(row["review_agreement"])


if __name__ == "__main__":
    unittest.main()
