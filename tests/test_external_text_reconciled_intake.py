import unittest

from src.isi.curation.external_text_reconciled_intake import materialize_reconciled_record


def source(branch: str) -> dict:
    evidence = {
        "evidence_id": "EVD_CASE_1",
        "evidence_type": "regulator_warning" if branch == "CONFIRMED" else "official_registry",
        "source_url": "https://regulator.test/warning" if branch == "CONFIRMED" else "https://adviserinfo.sec.gov/firm/summary/123",
        "supports": ["SCAM_CLAIM"] if branch == "CONFIRMED" else ["IDENTITY"],
        "reviewed": False,
    }
    return {
        "case_id": "CASE_1",
        "ground_truth_status": "UNCERTAIN",
        "label_confidence": "LOW",
        "review_status": "IN_REVIEW",
        "review_rationale": "Draft",
        "artifact": {"text": "Observed text"},
        "evidence": [evidence],
    }


def ai(branch: str) -> dict:
    official = {"source_url": "https://regulator.test/warning"} if branch == "CONFIRMED" else {"crd": "123"}
    return {
        "case_id": "CASE_1",
        "branch": branch,
        "ai_review": {
            "status": "COMPLETED",
            "reviewer_type": "AI_AGENT",
            "reviewer_id": "Codex",
            "ready_for_human_adoption": True,
            "recommended_decision": branch,
            "recommended_confidence": "HIGH",
            "unresolved_hard_contradictions": [],
            "official_evidence": official,
            "rationale": "Evidence aligns.",
        },
    }


def adoption() -> dict:
    return {
        "adoption_id": "ADOPTION",
        "adopted_at": "2026-09-24T00:00:00+07:00",
        "adopter_role": "PROJECT_OWNER",
        "authorization_source": "User directed progression",
        "accepted_all_ai_recommendations": True,
        "independent_human_evidence_rereview_claimed": False,
        "scope": {"ai_adjudication_analysis_id": "AI_REVIEW"},
    }


class ExternalTextReconciledIntakeTests(unittest.TestCase):
    def test_confirmed_materialization_preserves_source_and_reviews_evidence(self):
        original = source("CONFIRMED")
        output = materialize_reconciled_record(original, ai("CONFIRMED"), adoption())
        self.assertEqual(original["ground_truth_status"], "UNCERTAIN")
        self.assertEqual(output["ground_truth_status"], "CONFIRMED")
        self.assertEqual(output["review_status"], "RECONCILED")
        self.assertTrue(output["evidence"][0]["reviewed"])
        self.assertFalse(output["review_provenance"]["independent_human_evidence_rereview"])

    def test_legitimate_adds_reviewed_legitimacy_support(self):
        output = materialize_reconciled_record(source("LEGITIMATE"), ai("LEGITIMATE"), adoption())
        self.assertIn("LEGITIMACY", output["evidence"][0]["supports"])
        self.assertTrue(output["external_evaluation_eligible"])

    def test_unaccepted_recommendations_are_rejected(self):
        record = adoption()
        record["accepted_all_ai_recommendations"] = False
        with self.assertRaises(ValueError):
            materialize_reconciled_record(source("CONFIRMED"), ai("CONFIRMED"), record)

    def test_human_rereview_cannot_be_falsely_claimed(self):
        record = adoption()
        record["independent_human_evidence_rereview_claimed"] = True
        with self.assertRaises(ValueError):
            materialize_reconciled_record(source("CONFIRMED"), ai("CONFIRMED"), record)


if __name__ == "__main__":
    unittest.main()

