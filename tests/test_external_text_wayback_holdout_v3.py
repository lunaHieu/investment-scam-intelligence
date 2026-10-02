import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_external_text_wayback_holdout_v3_queue import (
    load_opened_benchmark_hosts,
    to_acquisition_row,
)
from scripts.audit_wayback_holdout_v3_captures import select_largest_balanced
from scripts.prepare_wayback_holdout_v3_second_review import build_v3_blind_packet
from src.isi.normalization.external_references import sha256_file


class ExternalTextWaybackHoldoutV3Tests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_acquisition_row_is_unlabeled_and_model_ineligible(self):
        source = {
            "candidate_id": "SOURCE_1",
            "candidate_host": "WWW.Example.COM.",
            "source_id": "sec_iapd",
            "source_record_id": "123",
            "entity_name_keys": ["example"],
            "official_reference": {"url": "https://example.invalid/reference"},
        }
        row = to_acquisition_row(
            source,
            branch="LEGITIMATE_CANDIDATE",
            rank=1,
            target_timestamp="20261002",
        )
        self.assertEqual(row["candidate_id"], "MATCHWB3_LEGIT_001")
        self.assertEqual(row["candidate_host"], "example.com")
        self.assertFalse(row["reference_branch_is_ground_truth"])
        self.assertFalse(row["label_created"])
        self.assertEqual(row["training_eligible"], "NO")
        self.assertTrue(row["model_scoring_eligible"].startswith("NO_"))

    def test_opened_benchmark_loader_verifies_hash_and_unique_hosts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "benchmark.json"
            path.write_text(
                json.dumps({
                    "records": [
                        {"artifact": {"candidate_host": "www.a.example"}},
                        {"artifact": {"candidate_host": "b.example"}},
                    ]
                }),
                encoding="utf-8",
            )
            protocol = {
                "opened_benchmark": {
                    "path": str(path),
                    "sha256": sha256_file(path),
                    "record_count": 2,
                }
            }
            hosts, report = load_opened_benchmark_hosts(protocol)
            self.assertEqual(hosts, {"a.example", "b.example"})
            self.assertEqual(report["unique_host_count"], 2)

    def test_opened_benchmark_loader_rejects_hash_change(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "benchmark.json"
            path.write_text('{"records": []}', encoding="utf-8")
            protocol = {
                "opened_benchmark": {
                    "path": str(path),
                    "sha256": "0" * 64,
                    "record_count": 0,
                }
            }
            with self.assertRaises(ValueError):
                load_opened_benchmark_hosts(protocol)

    def test_largest_balanced_usable_view_uses_smaller_branch(self):
        captures = []
        audits = []
        for branch, count in (("CONFIRMED_CANDIDATE", 2), ("LEGITIMATE_CANDIDATE", 3)):
            for index in range(count):
                candidate_id = f"{branch}-{index}"
                captures.append({
                    "candidate_id": candidate_id,
                    "reference_branch": branch,
                    "sha256": f"hash-{candidate_id}",
                })
                audits.append({
                    "candidate_id": candidate_id,
                    "audit_state": "HASH_VERIFIED_READABLE",
                })
        selected, per_branch = select_largest_balanced(
            captures, audits, minimum_per_branch=2, seed="fixed"
        )
        self.assertEqual(per_branch, 2)
        self.assertEqual(len(selected), 4)

    def test_largest_balanced_usable_view_enforces_minimum(self):
        captures = [
            {"candidate_id": "c", "reference_branch": "CONFIRMED_CANDIDATE", "sha256": "c"},
            {"candidate_id": "l", "reference_branch": "LEGITIMATE_CANDIDATE", "sha256": "l"},
        ]
        audits = [
            {"candidate_id": "c", "audit_state": "HASH_VERIFIED_READABLE"},
            {"candidate_id": "l", "audit_state": "HASH_VERIFIED_READABLE"},
        ]
        with self.assertRaises(ValueError):
            select_largest_balanced(captures, audits, minimum_per_branch=2, seed="fixed")

    def test_v3_blind_packet_is_balanced_and_uses_v3_ids(self):
        items = []
        reviews = []
        for candidate_id, decision in (("C1", "CONFIRMED"), ("C2", "CONFIRMED"), ("L1", "LEGITIMATE")):
            items.append({
                "candidate_id": candidate_id,
                "candidate_host": f"{candidate_id.casefold()}.example",
                "capture_stratum": "WAYBACK_ARCHIVED_HOMEPAGE_HTML",
                "artifact": {"visible_text": candidate_id, "text_sha256": f"text-{candidate_id}", "capture_sha256": f"capture-{candidate_id}"},
                "official_reference": {"url": "https://example.invalid"},
                "official_reference_record": {"observed_hosts": [f"{candidate_id.casefold()}.example"]},
                "entity_name_keys": [candidate_id],
            })
            reviews.append({
                "candidate_id": candidate_id,
                "evidence_decision": decision,
                "confidence": "HIGH",
                "language_decision": "ENGLISH",
                "artifact_text_sha256": f"text-{candidate_id}",
                "capture_sha256": f"capture-{candidate_id}",
            })
        packet, mapping, counts = build_v3_blind_packet({"items": items}, {"reviews": reviews}, seed="fixed")
        self.assertEqual(packet["packet_id"], "EXTERNAL_TEXT_WAYBACK_HOLDOUT_BLIND_SECOND_REVIEW_V3")
        self.assertEqual(counts["selected_per_class"], 1)
        self.assertEqual(len(packet["items"]), 2)
        self.assertEqual(len(mapping), 2)
        self.assertTrue(all(row["blind_review_id"].startswith("WB3BR_") for row in packet["items"]))
        def keys(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    yield key
                    yield from keys(child)
            elif isinstance(value, list):
                for child in value:
                    yield from keys(child)
        self.assertNotIn("candidate_id", set(keys(packet)))

    def test_checked_in_v3_registry_keeps_scoring_and_training_closed(self):
        registry = json.loads(
            (self.ROOT / "registry/pilots/external_text_wayback_holdout_benchmark_v3.json").read_text(encoding="utf-8")
        )
        self.assertEqual(registry["status"], "FROZEN_OWNER_ACCEPTANCE_REQUIRED_BEFORE_MODEL_SCORING")
        self.assertEqual(registry["counts"]["confirmed_high_agreements"], 15)
        self.assertEqual(registry["counts"]["legitimate_high_agreements"], 15)
        self.assertEqual(registry["counts"]["benchmark_records"], 30)
        self.assertFalse(registry["gates"]["owner_acceptance_complete"])
        self.assertFalse(registry["gates"]["model_scoring_allowed"])
        self.assertFalse(registry["gates"]["training_allowed"])
        self.assertFalse(registry["review_disclosure"]["independent_human_review_complete"])

    def test_manual_language_review_overrides_automatic_routing(self):
        policy = json.loads(
            (self.ROOT / "configs/external_text_wayback_holdout_primary_review_policy_v3.json").read_text(encoding="utf-8")
        )
        self.assertIn("MATCHWB3_CONF_081", policy["language_decisions"]["NON_ENGLISH"])
        self.assertIn("MATCHWB3_LEGIT_067", policy["language_decisions"]["ENGLISH"])
        self.assertNotIn("MATCHWB3_LEGIT_067", policy["language_decisions"]["NON_ENGLISH"])


if __name__ == "__main__":
    unittest.main()
