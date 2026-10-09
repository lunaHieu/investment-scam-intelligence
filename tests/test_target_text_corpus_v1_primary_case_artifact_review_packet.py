import unittest
from pathlib import Path

from scripts.build_target_text_corpus_v1_primary_case_artifact_review_packet import build


ROOT = Path(__file__).resolve().parents[1]


class TargetTextCorpusPrimaryCaseArtifactReviewPacketTests(unittest.TestCase):
    def test_frozen_packet_builds_with_complete_local_evidence(self) -> None:
        packet = build(ROOT / "configs" / "target_text_corpus_v1_primary_case_artifact_review_v1.json")
        self.assertEqual(packet["record_count"], 22)
        self.assertTrue(all(row["capture"]["text"] for row in packet["records"]))
        self.assertTrue(all(row["official_evidence"] for row in packet["records"]))
        self.assertTrue(all(row["review_form"]["label_created"] is False for row in packet["records"]))

    def test_edgar_channel_includes_iapd_evidence_and_caution(self) -> None:
        packet = build(ROOT / "configs" / "target_text_corpus_v1_primary_case_artifact_review_v1.json")
        edgar = [row for row in packet["records"] if "EDGAR" in row["channel_id"]]
        self.assertEqual(len(edgar), 8)
        self.assertTrue(all("registration_reference" in row["official_evidence"] for row in edgar))
        self.assertTrue(all("crosswalk_caution" in row["official_evidence"] for row in edgar))


if __name__ == "__main__":
    unittest.main()
