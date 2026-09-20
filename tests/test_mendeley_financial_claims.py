import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from extract_mendeley_financial_claims import (
    FEATURE_VERSION,
    FEATURE_VERSION_V2,
    FEATURE_VERSION_V3,
    FEATURE_VERSION_V4,
    compact_excerpt,
    extract_signals,
    rule_set_sha256,
    select_review_queue,
)


class MendeleyFinancialClaimsTests(unittest.TestCase):
    def signal_types(self, text, feature_version=FEATURE_VERSION):
        signals, _ = extract_signals(text, feature_version=feature_version)
        return {signal["signal_type"] for signal in signals}

    def rule_ids(self, text, feature_version=FEATURE_VERSION):
        signals, _ = extract_signals(text, feature_version=feature_version)
        return {signal["rule_id"] for signal in signals}

    def test_high_return_and_no_risk_are_separate_explainable_signals(self):
        signal_types = self.signal_types("Earn a guaranteed 30% return every week with no risk.")
        self.assertIn("RETURN_RATE", signal_types)
        self.assertIn("GUARANTEED_RETURN", signal_types)
        self.assertIn("NO_RISK", signal_types)

    def test_payment_and_crypto_connection_is_detected(self):
        signal_types = self.signal_types("Transfer your bitcoin to this wallet to start investing now.")
        self.assertIn("PAYMENT_OR_TRANSFER_REQUEST", signal_types)
        self.assertIn("CRYPTO_INVESTMENT_OR_PAYMENT", signal_types)
        self.assertIn("URGENCY_SCARCITY", signal_types)

    def test_vietnamese_signals_are_detected(self):
        signal_types = self.signal_types("Cam kết lợi nhuận 20% và không có rủi ro. Đầu tư ngay hôm nay.")
        self.assertIn("RETURN_RATE", signal_types)
        self.assertIn("GUARANTEED_RETURN", signal_types)
        self.assertIn("NO_RISK", signal_types)
        self.assertIn("URGENCY_SCARCITY", signal_types)

    def test_neutral_percentage_is_not_automatically_a_return_claim(self):
        signal_types = self.signal_types("The survey response rate was 30 percent last year.")
        self.assertNotIn("RETURN_RATE", signal_types)

    def test_equity_interest_is_not_return_rate(self):
        signal_types = self.signal_types("The group acquired a 66% interest in the subsidiary.")
        self.assertNotIn("RETURN_RATE", signal_types)

    def test_tax_returns_are_not_advance_fee(self):
        signal_types = self.signal_types("The candidate refuses to release his tax returns.")
        self.assertNotIn("ADVANCE_FEE_OR_WITHDRAWAL", signal_types)

    def test_referring_an_issue_to_a_commission_is_not_recruitment(self):
        signal_types = self.signal_types("Refer the rate issue to the regulatory commission.")
        self.assertNotIn("RECRUITMENT_REWARD", signal_types)

    def test_unlock_fee_is_detected(self):
        signal_types = self.signal_types("You are required to pay a tax to unlock your funds.")
        self.assertIn("ADVANCE_FEE_OR_WITHDRAWAL", signal_types)

    def test_crypto_return_multiple_is_detected(self):
        signal_types = self.signal_types("Ethereum is about to 1000x in the next year.")
        self.assertIn("RETURN_MULTIPLE", signal_types)
        self.assertIn("CRYPTO_INVESTMENT_OR_PAYMENT", signal_types)

    def test_review_excerpt_is_bounded(self):
        excerpt = compact_excerpt("word " * 100, limit=40)
        self.assertLessEqual(len(excerpt), 41)
        self.assertTrue(excerpt.endswith("…"))

    def test_queue_has_unique_groups_and_both_audit_reasons(self):
        records = []
        for index in range(150):
            records.append(
                {
                    "record_id": f"R{index}",
                    "partition": "train",
                    "split_group_id": f"G{index}",
                    "signal_types": ["NO_RISK"] if index < 100 else [],
                    "evidence_contexts": [],
                }
            )
        queue = select_review_queue(records, candidate_target=20, no_signal_target=10)
        self.assertEqual(len(queue), 30)
        self.assertEqual(len({item["split_group_id"] for item in queue}), 30)
        reasons = [item["queue_reason"] for item in queue]
        self.assertEqual(reasons.count("SIGNAL_CANDIDATE"), 20)
        self.assertEqual(reasons.count("NO_SIGNAL_AUDIT"), 10)

    def test_v1_rule_hash_remains_frozen(self):
        self.assertEqual(
            rule_set_sha256(FEATURE_VERSION),
            "3e0f13e55b5755d4307ee1991e9a3190834b245a609dd6cbbd173a9ce36fabb7",
        )
        self.assertNotEqual(rule_set_sha256(FEATURE_VERSION_V2), rule_set_sha256(FEATURE_VERSION))

    def test_v2_rule_hash_remains_frozen(self):
        self.assertEqual(
            rule_set_sha256(FEATURE_VERSION_V2),
            "e462fae5e77320bd5c50c38d56e3068248c86cc177bac7d17bc30314d6fef71a",
        )
        self.assertNotEqual(rule_set_sha256(FEATURE_VERSION_V3), rule_set_sha256(FEATURE_VERSION_V2))

    def test_v2_excludes_double_digit_rate_from_return_multiple(self):
        text = "This opportunity offers double - digit monthly returns of 10-30%."
        self.assertIn("RETURN_MULTIPLE", self.signal_types(text, FEATURE_VERSION))
        v2_types = self.signal_types(text, FEATURE_VERSION_V2)
        self.assertNotIn("RETURN_MULTIPLE", v2_types)
        self.assertIn("RETURN_RATE", v2_types)

    def test_v2_excludes_no_risk_or_obligation_form_language(self):
        text = "The information is free and comes under no risk or obligations."
        self.assertIn("NO_RISK", self.signal_types(text, FEATURE_VERSION))
        self.assertNotIn("NO_RISK", self.signal_types(text, FEATURE_VERSION_V2))

    def test_v2_excludes_risk_free_rate_terminology(self):
        text = "The model compares discounting and risk free rates."
        self.assertIn("NO_RISK", self.signal_types(text, FEATURE_VERSION))
        self.assertNotIn("NO_RISK", self.signal_types(text, FEATURE_VERSION_V2))

    def test_v2_excludes_negated_payment_instruction(self):
        text = "Please do not send postal money orders."
        self.assertIn("PAYMENT_OR_TRANSFER_REQUEST", self.signal_types(text, FEATURE_VERSION))
        self.assertNotIn("PAYMENT_OR_TRANSFER_REQUEST", self.signal_types(text, FEATURE_VERSION_V2))

    def test_v2_excludes_negated_get_rich_quick_phrase(self):
        text = "This is not a get rich quick scheme."
        self.assertIn("PASSIVE_OR_EASY_INCOME", self.signal_types(text, FEATURE_VERSION))
        self.assertNotIn("PASSIVE_OR_EASY_INCOME", self.signal_types(text, FEATURE_VERSION_V2))

    def test_v2_excludes_discount_percentage_from_return_rate(self):
        text = "You can invest $66.50, a 33% discount off the usual price, to earn income."
        self.assertIn("RETURN_RATE", self.signal_types(text, FEATURE_VERSION))
        v2_types = self.signal_types(text, FEATURE_VERSION_V2)
        self.assertNotIn("RETURN_RATE", v2_types)
        self.assertIn("MONEY_AMOUNT", v2_types)

    def test_v2_preserves_true_positive_examples(self):
        cases = (
            ("Ethereum is about to 1000x in the next year.", "RETURN_MULTIPLE"),
            ("Guaranteed returns with no risk at all.", "NO_RISK"),
            ("Please send me bitcoin to start investing.", "PAYMENT_OR_TRANSFER_REQUEST"),
            ("Earn a 30% return every month.", "RETURN_RATE"),
            ("Build passive income with this investment.", "PASSIVE_OR_EASY_INCOME"),
        )
        for text, expected in cases:
            with self.subTest(text=text, expected=expected):
                self.assertIn(expected, self.signal_types(text, FEATURE_VERSION_V2))

    def test_v3_excludes_working_interest_percentage(self):
        text = "Each well earns Emerson a 49% working interest in one section."
        self.assertIn("RETURN_RATE", self.signal_types(text, FEATURE_VERSION_V2))
        self.assertNotIn("RETURN_RATE", self.signal_types(text, FEATURE_VERSION_V3))

    def test_v3_excludes_government_contract_guarantee(self):
        text = "The company again invoked the state government's guarantee under the contract."
        self.assertIn("GUARANTEED_RETURN", self.signal_types(text, FEATURE_VERSION_V2))
        self.assertNotIn("GUARANTEED_RETURN", self.signal_types(text, FEATURE_VERSION_V3))

    def test_v3_excludes_product_refund_no_risk_wording(self):
        text = "The e-book comes with a no risk full year money-back guarantee."
        self.assertIn("NO_RISK", self.signal_types(text, FEATURE_VERSION_V2))
        self.assertNotIn("NO_RISK", self.signal_types(text, FEATURE_VERSION_V3))

    def test_v3_excludes_riskfree_curve_terminology(self):
        text = "We use LIBOR as the benchmark riskfree curve."
        self.assertIn("NO_RISK", self.signal_types(text, FEATURE_VERSION_V2))
        self.assertNotIn("NO_RISK", self.signal_types(text, FEATURE_VERSION_V3))

    def test_v3_detects_longer_crypto_growth_claim(self):
        text = "Ethereum is about to skyrocket! My team has insider info that it will jump 50x soon."
        v2_types = self.signal_types(text, FEATURE_VERSION_V2)
        self.assertNotIn("RETURN_MULTIPLE", v2_types)
        self.assertNotIn("CRYPTO_INVESTMENT_OR_PAYMENT", v2_types)
        v3_types = self.signal_types(text, FEATURE_VERSION_V3)
        self.assertIn("RETURN_MULTIPLE", v3_types)
        self.assertIn("CRYPTO_INVESTMENT_OR_PAYMENT", v3_types)

    def test_v3_detects_nft_growth_claim(self):
        text = "NFT is about to skyrocket and it will jump 10x in a few weeks."
        v3_types = self.signal_types(text, FEATURE_VERSION_V3)
        self.assertIn("RETURN_MULTIPLE", v3_types)
        self.assertIn("CRYPTO_INVESTMENT_OR_PAYMENT", v3_types)

    def test_v3_detects_turn_amount_into_larger_amount(self):
        text = "This investment can turn $500 into $5000 in a week."
        self.assertNotIn("RETURN_MULTIPLE", self.signal_types(text, FEATURE_VERSION_V2))
        self.assertIn("RETURN_MULTIPLE", self.signal_types(text, FEATURE_VERSION_V3))

    def test_v3_rejects_non_increasing_turn_amount(self):
        cases = (
            "Turning $300 into $20 would lose money.",
            "Turn $1000 into $1000 with no change.",
        )
        for text in cases:
            with self.subTest(text=text):
                self.assertNotIn("RETURN_MULTIPLE", self.signal_types(text, FEATURE_VERSION_V3))

    def test_v3_crypto_earnings_rule_does_not_treat_stock_as_crypto(self):
        text = "The stock market made me $94 this month."
        self.assertNotIn("CRYPTO_INVESTMENT_OR_PAYMENT", self.signal_types(text, FEATURE_VERSION_V3))

    def test_v3_detects_crypto_or_nft_earnings_claim(self):
        cases = (
            "Made $100K last month with a secret Bitcoin system.",
            "Earned $20K through an NFT system.",
        )
        for text in cases:
            with self.subTest(text=text):
                self.assertNotIn("CRYPTO_INVESTMENT_OR_PAYMENT", self.signal_types(text, FEATURE_VERSION_V2))
                self.assertIn("CRYPTO_INVESTMENT_OR_PAYMENT", self.signal_types(text, FEATURE_VERSION_V3))

    def test_v3_preserves_investment_no_risk_and_guaranteed_return(self):
        text = "Guaranteed 20% investment return with no risk."
        signal_types = self.signal_types(text, FEATURE_VERSION_V3)
        self.assertIn("RETURN_RATE", signal_types)
        self.assertIn("GUARANTEED_RETURN", signal_types)
        self.assertIn("NO_RISK", signal_types)

    def test_v3_rule_hash_remains_frozen(self):
        self.assertEqual(
            rule_set_sha256(FEATURE_VERSION_V3),
            "1ab63dde22f35083772eafd8f3bcde344ffe95d3c3e91c2f8d326646c830bd11",
        )
        self.assertNotEqual(rule_set_sha256(FEATURE_VERSION_V4), rule_set_sha256(FEATURE_VERSION_V3))

    def test_v4_excludes_negated_turn_amount_claim(self):
        text = "You're not going to turn $2 into $5 in a week, so cash out when you're ahead."
        self.assertIn("RETURN_MULTIPLE", self.signal_types(text, FEATURE_VERSION_V3))
        self.assertNotIn("RETURN_MULTIPLE", self.signal_types(text, FEATURE_VERSION_V4))

    def test_v4_excludes_rejected_no_risk_audience(self):
        cases = (
            "If you're looking for a retirement investment with no risk that goes up 5% a year, this ain't your kind.",
            "If you ' re looking for an investment with no risk, this ain ' t your kind.",
        )
        for text in cases:
            with self.subTest(text=text):
                self.assertIn("NO_RISK", self.signal_types(text, FEATURE_VERSION_V3))
                self.assertNotIn("NO_RISK", self.signal_types(text, FEATURE_VERSION_V4))

    def test_v4_excludes_income_distribution_percentages(self):
        text = "Average income of a day trader: 5% average an income above $500,000 per year."
        self.assertIn("RETURN_RATE", self.signal_types(text, FEATURE_VERSION_V3))
        self.assertNotIn("RETURN_RATE", self.signal_types(text, FEATURE_VERSION_V4))

    def test_v4_detects_nft_rocket_multiple_and_urgency(self):
        text = "ATTENTION! NFT is about to 🚀 5x in the next 6 months! DM me for the insider info!"
        types = self.signal_types(text, FEATURE_VERSION_V4)
        self.assertIn("RETURN_MULTIPLE", types)
        self.assertIn("CRYPTO_INVESTMENT_OR_PAYMENT", types)
        self.assertIn("URGENCY_SCARCITY", types)
        rules = self.rule_ids(text, FEATURE_VERSION_V4)
        self.assertIn("FCV4_RETURN_MULTIPLE_ROCKET_01", rules)
        self.assertIn("FCV4_CRYPTO_ROCKET_01", rules)
        self.assertIn("FCV4_URGENCY_ATTENTION_DM_01", rules)

    def test_v4_detects_trading_rocket_without_crypto(self):
        text = "ATTENTION! trading is about to 🚀 10x in the next so long! DM me for the insider info!"
        types = self.signal_types(text, FEATURE_VERSION_V4)
        self.assertIn("RETURN_MULTIPLE", types)
        self.assertIn("URGENCY_SCARCITY", types)
        self.assertNotIn("CRYPTO_INVESTMENT_OR_PAYMENT", types)

    def test_v4_detects_guaranteed_annuity_rate_but_not_mortgage_guarantee(self):
        annuity = "Very Competitive Rates Guaranteed 6 Years. Let AIG's Annuity Portfolio Work for You!"
        mortgage = "We can guarantee you the lowest possible rate on your home loan."
        self.assertIn("GUARANTEED_RETURN", self.signal_types(annuity, FEATURE_VERSION_V4))
        self.assertNotIn("GUARANTEED_RETURN", self.signal_types(mortgage, FEATURE_VERSION_V4))


if __name__ == "__main__":
    unittest.main()
