import unittest

from scripts.build_matched_wayback_expansion_queue import host_from_url
from scripts.build_matched_wayback_legitimate_supplement import select_supplement
from scripts.prepare_matched_wayback_second_review import (
    assert_blind_packet,
    blind_id,
)
from scripts.record_matched_wayback_supplement_first_review import validate_decisions
from scripts.record_matched_wayback_second_review import validate_reviews
from scripts.reconcile_matched_wayback_benchmark import reconcile


class MatchedWaybackExternalBenchmarkTests(unittest.TestCase):
    def test_host_from_wayback_raw_replay_uses_original_host(self):
        self.assertEqual(
            host_from_url(
                "https://web.archive.org/web/20260420093322id_/https://www.alpha-flow.ai/"
            ),
            "alpha-flow.ai",
        )

    def test_host_from_live_reference_removes_www_only(self):
        self.assertEqual(host_from_url("https://www.example.com/path"), "example.com")

    def test_invalid_host_is_rejected(self):
        with self.assertRaises(ValueError):
            host_from_url("not-a-url")

    def test_blind_id_is_deterministic_and_opaque(self):
        first = blind_id("seed", "MATCHWB_CASE_001")
        self.assertEqual(first, blind_id("seed", "MATCHWB_CASE_001"))
        self.assertTrue(first.startswith("BRV1_"))
        self.assertNotIn("CASE", first)

    def test_blind_packet_rejects_label_leakage(self):
        with self.assertRaises(ValueError):
            assert_blind_packet({"items": [{"reference_status": "CONFIRMED"}]})

    def test_supplement_excludes_existing_hosts_and_preserves_candidate_state(self):
        row = {
            "candidate_id": "EXTCAP_RESERVE_LEGIT_011",
            "candidate_host": "new.example",
            "source_record_id": "11",
            "target_outcome": "LEGITIMATE_RESERVE_CANDIDATE",
            "selection_rank_within_target": 11,
            "entity_name_keys": ["new example advisors"],
            "official_reference": {
                "registration": {"firm_type": "Registered", "status": "APPROVED"}
            },
        }
        self.assertEqual(select_supplement([row], {"old.example"}, 1)[0]["label_created"], False)
        self.assertEqual(select_supplement([row], {"new.example"}, 1), [])

    def test_first_review_rejects_target_decision_with_contradiction(self):
        packet = {
            "items": [
                {
                    "candidate_id": "C1",
                    "allowed_decisions": ["LEGITIMATE", "UNCERTAIN"],
                    "artifact": {"text_sha256": "a", "source_capture_sha256": "b"},
                    "screening": {
                        "screening_decision": "REVIEWABLE_OBSERVED_TEXT",
                        "snapshot_predates_registration": False,
                    },
                }
            ]
        }
        decisions = {
            "review_type": "AI_PRIMARY_REVIEW_NOT_HUMAN",
            "model_outputs_consulted": False,
            "reviewer": "r",
            "reviewed_at": "2026-09-24T00:00:00+07:00",
            "decisions": [
                {
                    "candidate_id": "C1",
                    "decision": "LEGITIMATE",
                    "confidence": "HIGH",
                    "rationale": "r",
                    "contradictions": ["unresolved"],
                }
            ],
        }
        with self.assertRaises(ValueError):
            validate_decisions(packet, decisions)

    def test_second_review_requires_exact_blind_coverage(self):
        packet = {
            "items": [
                {
                    "blind_review_id": "B1",
                    "review_contract": {
                        "allowed_decisions": ["LEGITIMATE"],
                        "decision_confidence": ["HIGH"],
                    },
                }
            ]
        }
        response = {
            "review_type": "INDEPENDENT_BLINDED_AI_SECOND_REVIEW_NOT_HUMAN",
            "reviewer": "OpenAI Codex independent blinded AI reviewer",
            "reviews": [],
        }
        with self.assertRaises(ValueError):
            validate_reviews(packet, response)

    def test_reconciliation_balances_agreed_classes(self):
        candidates = []
        mappings = []
        reviews = []
        for index, status in enumerate(("CONFIRMED", "CONFIRMED", "LEGITIMATE"), start=1):
            candidate_id = f"C{index}"
            blind = f"B{index}"
            candidates.append(
                {
                    "candidate_id": candidate_id,
                    "artifact": {"text_sha256": f"t{index}", "source_capture_sha256": f"c{index}"},
                    "evidence": [],
                }
            )
            mappings.append(
                {
                    "blind_review_id": blind,
                    "candidate_id": candidate_id,
                    "reference_status": status,
                    "artifact_text_sha256": f"t{index}",
                    "capture_sha256": f"c{index}",
                }
            )
            reviews.append(
                {
                    "blind_review_id": blind,
                    "decision": status,
                    "confidence": "HIGH",
                    "contradictions": [],
                    "rationale": "aligned",
                }
            )
        records, nonagreements, counts = reconcile(candidates, mappings, reviews, "seed")
        self.assertEqual(counts["matched_per_class"], 1)
        self.assertEqual(len(records), 2)
        self.assertEqual(nonagreements, [])


if __name__ == "__main__":
    unittest.main()
