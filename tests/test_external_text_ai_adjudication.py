import unittest

from src.isi.curation.external_text_ai_adjudication import build_ai_adjudication_record


def form(branch: str) -> dict:
    return {
        "case_id": "CASE_1",
        "branch": branch,
        "candidate_host": "example.test",
        "source_packet": {"analysis_id": "PACKET", "sha256": "a" * 64},
        "automated_context": {"proposed_outcome": branch},
        "review_contract": {"required_checks": ["raw_and_text_hashes_verified"]},
        "human_review": {"status": "PENDING", "human_confirmation_recorded": False},
        "label_created": False,
        "external_evaluation_eligible": False,
    }


def packet(branch: str) -> dict:
    base = {
        "case_id": "CASE_1",
        "contradiction_review": {"hard_contradictions": [], "caution_flags": ["CAUTION"]},
    }
    if branch == "CONFIRMED":
        base["regulator_evidence"] = {"url": "https://regulator.test/warning"}
    else:
        base["sec_identity_and_registration"] = {
            "crd": "123",
            "captured_host_exactly_listed": True,
        }
    return base


def spec(branch: str) -> dict:
    evidence = {
        "review_status": "REVIEWED",
        "exact_candidate_alignment": True,
    }
    if branch == "CONFIRMED":
        evidence["source_url"] = "https://regulator.test/warning"
    else:
        evidence["crd"] = "123"
    return {
        "case_id": "CASE_1",
        "reviewed_at": "2026-09-24T00:00:00+07:00",
        "authorization": "Explicit user authorization",
        "recommended_decision": branch,
        "recommended_confidence": "HIGH",
        "rationale": "Evidence aligns without a hard contradiction.",
        "official_evidence": evidence,
        "caution_dispositions": {"CAUTION": "Reviewed and resolved within scope."},
        "residual_limitations": ["Human confirmation remains separate."],
    }


class ExternalTextAIAdjudicationTests(unittest.TestCase):
    def test_ai_review_never_opens_human_or_label_gates(self):
        result = build_ai_adjudication_record(
            form("CONFIRMED"), packet("CONFIRMED"), spec("CONFIRMED")
        )
        self.assertEqual(result["ai_review"]["status"], "COMPLETED")
        self.assertTrue(result["ai_review"]["ready_for_human_adoption"])
        self.assertEqual(result["human_review"]["status"], "PENDING")
        self.assertFalse(result["human_review"]["human_confirmation_recorded"])
        self.assertFalse(result["ready_for_reconciled_intake"])
        self.assertFalse(result["label_created"])
        self.assertFalse(result["external_evaluation_eligible"])

    def test_legitimate_requires_matching_crd(self):
        bad = spec("LEGITIMATE")
        bad["official_evidence"]["crd"] = "999"
        with self.assertRaises(ValueError):
            build_ai_adjudication_record(form("LEGITIMATE"), packet("LEGITIMATE"), bad)

    def test_every_caution_requires_disposition(self):
        bad = spec("CONFIRMED")
        bad["caution_dispositions"] = {}
        with self.assertRaises(ValueError):
            build_ai_adjudication_record(form("CONFIRMED"), packet("CONFIRMED"), bad)

    def test_human_review_must_still_be_pending(self):
        source = form("CONFIRMED")
        source["human_review"]["status"] = "COMPLETED"
        with self.assertRaises(ValueError):
            build_ai_adjudication_record(source, packet("CONFIRMED"), spec("CONFIRMED"))


if __name__ == "__main__":
    unittest.main()

