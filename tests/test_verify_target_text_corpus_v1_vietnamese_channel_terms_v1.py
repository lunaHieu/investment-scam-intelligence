import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_vietnamese_channel_terms_v1 import verify


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "configs" / "target_text_corpus_v1_vietnamese_channel_terms_v1.json"


class VerifyTargetTextCorpusV1VietnameseChannelTermsV1Tests(unittest.TestCase):
    def test_protocol_registers_both_source_roles_and_keeps_acquisition_closed(self) -> None:
        result = verify(PROTOCOL)
        self.assertEqual(result["status"], "PASS_SOURCE_ROLES_REGISTERED_ACQUISITION_AND_MATRIX_BLOCKED")
        self.assertEqual(result["checks"]["source_count"], 2)
        self.assertEqual(result["checks"]["target_status_count"], 2)
        self.assertTrue(result["checks"]["source_role_registration_gate_passed"])
        self.assertFalse(result["checks"]["reference_acquisition_gate_passed"])
        self.assertTrue(result["checks"]["sampling_matrix_v2_required"])
        self.assertEqual(result["errors"], [])


if __name__ == "__main__":
    unittest.main()
