import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from extract_mendeley_financial_claims import compact_excerpt, extract_signals, select_review_queue


class MendeleyFinancialClaimsTests(unittest.TestCase):
    def signal_types(self, text):
        signals, _ = extract_signals(text)
        return {signal["signal_type"] for signal in signals}

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


if __name__ == "__main__":
    unittest.main()
