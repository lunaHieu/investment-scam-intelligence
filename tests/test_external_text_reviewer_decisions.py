import unittest

from src.isi.curation.external_text_reviewer_decisions import (
    build_pending_review_record,
    record_human_decision,
)


def packet_record(branch: str) -> dict:
    target = "CONFIRMED" if branch == "CONFIRMED" else "LEGITIMATE"
    return {
        "case_id": f"CASE_{branch}_001",
        "candidate_host": "example.test",
        "source_state": {
            "ground_truth_status": "UNCERTAIN",
            "label_confidence": "LOW",
            "review_status": "IN_REVIEW",
            "record_state_changed": False,
        },
        "contradiction_review": {
            "hard_contradictions": [],
            "caution_flags": ["MANUAL_CHECK_REQUIRED"],
        },
        "automated_second_pass": {
            "proposed_outcome_for_human_review": target,
            "recommendation_confidence": "HIGH_FOR_HUMAN_REVIEW",
            "recommendation_is_ground_truth": False,
        },
        "external_evaluation_eligible": False,
    }


class ExternalTextReviewerDecisionTests(unittest.TestCase):
    def test_pending_form_contains_no_human_decision_or_label(self):
        form = build_pending_review_record(
            packet_record("CONFIRMED"),
            branch="CONFIRMED",
            packet_analysis_id="PACKET",
            packet_sha256="a" * 64,
        )
        self.assertEqual(form["human_review"]["status"], "PENDING")
        self.assertIsNone(form["human_review"]["final_decision"])
        self.assertTrue(all(value is None for value in form["evidence_confirmations"].values()))
        self.assertFalse(form["label_created"])
        self.assertFalse(form["external_evaluation_eligible"])

    def test_completed_target_decision_is_ready_but_does_not_mutate_intake(self):
        form = build_pending_review_record(
            packet_record("LEGITIMATE"),
            branch="LEGITIMATE",
            packet_analysis_id="PACKET",
            packet_sha256="b" * 64,
        )
        completed = record_human_decision(
            form,
            decision="LEGITIMATE",
            confidence="HIGH",
            reviewer="Reviewer A",
            reviewed_at="2026-09-24",
            rationale="Verified the filed host, identity, site control, and contradictions.",
            confirmation_source="Local packet plus manually opened SEC/IAPD reference",
            confirm_all_checks=True,
            confirm_human_review=True,
        )
        self.assertTrue(completed["ready_for_reconciled_intake"])
        self.assertFalse(completed["source_intake_changed"])
        self.assertFalse(completed["label_created"])
        self.assertFalse(completed["external_evaluation_eligible"])

    def test_branch_mismatch_is_rejected(self):
        form = build_pending_review_record(
            packet_record("CONFIRMED"),
            branch="CONFIRMED",
            packet_analysis_id="PACKET",
            packet_sha256="c" * 64,
        )
        with self.assertRaises(ValueError):
            record_human_decision(
                form,
                decision="LEGITIMATE",
                confidence="HIGH",
                reviewer="Reviewer A",
                reviewed_at="2026-09-24",
                rationale="Wrong branch.",
                confirmation_source="Manual review",
                confirm_all_checks=True,
                confirm_human_review=True,
            )

    def test_target_decision_rejects_unresolved_contradictions(self):
        form = build_pending_review_record(
            packet_record("CONFIRMED"),
            branch="CONFIRMED",
            packet_analysis_id="PACKET",
            packet_sha256="d" * 64,
        )
        with self.assertRaises(ValueError):
            record_human_decision(
                form,
                decision="CONFIRMED",
                confidence="HIGH",
                reviewer="Reviewer A",
                reviewed_at="2026-09-24",
                rationale="Warning may refer to a different entity.",
                confirmation_source="Manual review",
                confirm_all_checks=True,
                confirm_human_review=True,
                unresolved_contradictions=["Entity scope is unresolved"],
            )

    def test_uncertain_decision_can_preserve_unresolved_issue(self):
        form = build_pending_review_record(
            packet_record("CONFIRMED"),
            branch="CONFIRMED",
            packet_analysis_id="PACKET",
            packet_sha256="e" * 64,
        )
        completed = record_human_decision(
            form,
            decision="UNCERTAIN",
            confidence="LOW",
            reviewer="Reviewer A",
            reviewed_at="2026-09-24",
            rationale="Insufficient evidence to reconcile the entity.",
            confirmation_source="Manual review",
            confirm_all_checks=True,
            confirm_human_review=True,
            unresolved_contradictions=["Entity scope is unresolved"],
        )
        self.assertFalse(completed["ready_for_reconciled_intake"])
        self.assertEqual(
            completed["human_review"]["unresolved_contradictions"],
            ["Entity scope is unresolved"],
        )


if __name__ == "__main__":
    unittest.main()
