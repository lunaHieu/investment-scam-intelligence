import json
import unittest
from pathlib import Path

from scripts.build_target_text_corpus_v1_blind_second_review_packet import build, opaque_id


ROOT = Path(__file__).resolve().parents[1]


class TargetTextCorpusBlindSecondReviewPacketTests(unittest.TestCase):
    def test_opaque_id_is_deterministic_and_namespace_bound(self) -> None:
        first = opaque_id("A", "candidate-1")
        self.assertEqual(first, opaque_id("A", "candidate-1"))
        self.assertNotEqual(first, opaque_id("B", "candidate-1"))
        self.assertNotIn("candidate", first.casefold())

    def test_blind_packet_omits_primary_and_source_stratum_fields(self) -> None:
        packet, mapping = build(ROOT / "configs" / "target_text_corpus_v1_blind_second_review_v1.json")
        self.assertEqual(packet["record_count"], 22)
        self.assertEqual(mapping["record_count"], 22)
        serialized = json.dumps(packet["records"], ensure_ascii=False).casefold()
        self.assertNotIn('"candidate_id"', serialized)
        self.assertNotIn('"channel_target_stratum"', serialized)
        self.assertNotIn('"primary_recommendation"', serialized)
        self.assertNotIn("ttcv1_cand_", serialized)
        self.assertNotIn('"text_path"', serialized)
        self.assertEqual(len({row["blind_id"] for row in packet["records"]}), 22)


if __name__ == "__main__":
    unittest.main()
