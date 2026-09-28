import unittest

from src.isi.curation.confirmed_reconciliation_review import (
    assess_reconciliation_record,
    classify_warning,
    profile_text_signals,
)


def record(text: str) -> dict:
    return {
        "case_id": "CASE_TEST",
        "ground_truth_status": "UNCERTAIN",
        "label_confidence": "LOW",
        "review_status": "IN_REVIEW",
        "artifact": {
            "text": text,
            "text_sha256": "a" * 64,
            "source_capture_path": "capture.html",
            "source_capture_sha256": "b" * 64,
        },
        "evidence": [{"reviewed": False}],
    }


def first_pass() -> dict:
    return {
        "candidate_id": "EXTCAP_TEST",
        "candidate_host": "example.test",
        "archive_snapshot": {
            "url": "https://web.archive.org/web/20260601000000id_/https://example.test/",
            "snapshot_observed_at": "2026-06-01T00:00:00+00:00",
            "candidate_host_match": True,
            "identity_token_check": {"any_full_token_match": True},
        },
        "official_warning": {
            "url": "https://regulator.test/warnings/example",
            "regulator": {"name": "Example Regulator", "jurisdiction": "Test"},
            "warning_categories": {
                "category": "1",
                "detail": "Unregistered/Unlicensed entity",
            },
            "validation_date": "2026-09-01",
            "local_capture_available": False,
            "candidate_identity_visible_in_local_capture": False,
        },
        "comparison": {"archive_snapshot_not_after_warning": True},
    }


class ConfirmedReconciliationReviewTests(unittest.TestCase):
    def test_profiles_solicitation_and_keeps_context_bounded(self):
        text = (
            "Example Capital offers cryptocurrency trading. Sign up and deposit $250. "
            "Earn a guaranteed 12% return. Capital is at risk."
        )
        profile = profile_text_signals(text)
        self.assertTrue(profile["investment_or_trading_offering"]["detected"])
        self.assertTrue(profile["account_or_action_call"]["detected"])
        self.assertTrue(profile["money_movement"]["detected"])
        self.assertTrue(profile["return_or_performance_claim"]["detected"])
        self.assertTrue(profile["risk_disclosure"]["detected"])
        for signal in profile.values():
            self.assertLessEqual(len(signal["bounded_contexts"]), 2)

    def test_all_gates_pass_without_creating_ground_truth(self):
        item = record(
            "Example Capital investment and crypto trading. Register now, deposit funds, "
            "and withdraw profits. Returns are not guaranteed and capital is at risk."
        )
        result = assess_reconciliation_record(
            item,
            first_pass(),
            raw_capture_hash_valid=True,
            text_hash_valid=True,
        )
        self.assertTrue(result["automated_second_pass"]["all_automatic_gates_pass"])
        self.assertEqual(
            result["automated_second_pass"]["proposed_outcome_for_human_review"],
            "CONFIRMED",
        )
        self.assertFalse(result["automated_second_pass"]["recommendation_is_ground_truth"])
        self.assertIsNone(result["human_decision"]["decision"])
        self.assertFalse(result["external_evaluation_eligible"])

    def test_identity_mismatch_is_a_hard_contradiction(self):
        report = first_pass()
        report["archive_snapshot"]["identity_token_check"]["any_full_token_match"] = False
        result = assess_reconciliation_record(
            record("Investment trading. Sign up and deposit now."),
            report,
            raw_capture_hash_valid=True,
            text_hash_valid=True,
        )
        self.assertIn(
            "candidate_identity_tokens_present",
            result["contradiction_review"]["hard_contradictions"],
        )
        self.assertEqual(
            result["automated_second_pass"]["proposed_outcome_for_human_review"],
            "UNCERTAIN",
        )

    def test_clone_url_classifies_uncategorized_warning(self):
        result = classify_warning(
            {"category": None, "detail": None},
            "https://regulator.test/warnings/example-clone-authorised-firm",
        )
        self.assertEqual(result["evidence_class"], "IMPERSONATION_OR_CLONE_WARNING")
        self.assertTrue(result["explicit_impersonation_or_clone_in_url"])

    def test_self_claim_is_a_caution_not_a_hard_contradiction(self):
        result = assess_reconciliation_record(
            record("Licensed and regulated investment platform. Sign up and deposit funds."),
            first_pass(),
            raw_capture_hash_valid=True,
            text_hash_valid=True,
        )
        self.assertIn(
            "CANDIDATE_PAGE_SELF_ASSERTS_REGULATION_LICENSE_OR_SAFETY",
            result["contradiction_review"]["caution_flags"],
        )
        self.assertEqual(result["contradiction_review"]["hard_contradictions"], [])

    def test_funded_account_call_to_action_supports_prop_trading_page(self):
        result = assess_reconciliation_record(
            record(
                "Kubera Prop Trading CFD Trading. Pass the challenge and upgrade to a "
                "Funded trading account. Start Here. Open CFD Account. Capital is at risk."
            ),
            first_pass(),
            raw_capture_hash_valid=True,
            text_hash_valid=True,
        )
        self.assertTrue(
            result["preserved_text_signal_profile"]["account_or_action_call"]["detected"]
        )
        self.assertTrue(result["automated_second_pass"]["all_automatic_gates_pass"])

    def test_impersonation_in_fragment_is_classified(self):
        result = classify_warning(
            {"category": None, "detail": None},
            "https://regulator.test/alert-list#!impersonation-of-example-firm",
        )
        self.assertEqual(result["evidence_class"], "IMPERSONATION_OR_CLONE_WARNING")


if __name__ == "__main__":
    unittest.main()
