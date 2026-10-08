import unittest
from pathlib import Path

from scripts.build_target_text_corpus_v1_manual_group_review_packet import EMAIL, PHONE, build


ROOT = Path(__file__).resolve().parents[1]


class TargetTextCorpusManualGroupReviewPacketTests(unittest.TestCase):
    def test_contact_indicators_are_extracted_without_label_inference(self) -> None:
        text = "Contact team@example.com or +1 (212) 555-0100 for details."
        self.assertEqual(EMAIL.findall(text), ["team@example.com"])
        self.assertTrue(PHONE.findall(text))

    def test_frozen_packet_population_builds_without_writing(self) -> None:
        packet = build(ROOT / "configs" / "target_text_corpus_v1_manual_group_review_v1.json")
        self.assertEqual(packet["record_count"], 22)
        self.assertTrue(all(row["review_form"]["label_created"] is False for row in packet["records"]))


if __name__ == "__main__":
    unittest.main()
