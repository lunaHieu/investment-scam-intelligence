import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.isi.matching.external_domain_references import (
    build_match_outputs,
    build_reference_maps,
    match_host,
    queue_reason,
)


ROOT = Path(__file__).resolve().parents[1]


def write_jsonl(path: Path, records):
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")


class CrimsonExternalReferenceMatchingTests(unittest.TestCase):
    def setUp(self):
        self.references = [
            {
                "source_id": "iosco_i_scan",
                "source_record_id": "A",
                "observed_hosts": ["example.com", "trade.example.com"],
                "reference_role": "REGULATOR_WARNING_EVIDENCE",
                "reference_semantics": "warning only",
            },
            {
                "source_id": "iosco_i_scan",
                "source_record_id": "B",
                "observed_hosts": ["shared.example"],
                "reference_role": "REGULATOR_WARNING_EVIDENCE",
                "reference_semantics": "warning only",
            },
        ]

    def test_exact_match_wins_over_hierarchy_for_same_reference_record(self):
        by_host, descendants = build_reference_maps(self.references, "iosco_i_scan")
        matches = match_host("www.trade.example.com", "iosco_i_scan", by_host, descendants)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["host_relation"], "EXACT_HOST")
        self.assertEqual(matches[0]["matched_reference_host"], "trade.example.com")

    def test_both_host_hierarchy_directions_are_candidates_not_identity_resolution(self):
        by_host, descendants = build_reference_maps(self.references, "iosco_i_scan")
        child = match_host("login.example.com", "iosco_i_scan", by_host, descendants)
        parent_references = [{
            "source_id": "iosco_i_scan", "source_record_id": "C",
            "observed_hosts": ["portal.other.example"], "reference_role": "warning",
            "reference_semantics": "warning only",
        }]
        parent_by_host, parent_descendants = build_reference_maps(parent_references, "iosco_i_scan")
        parent = match_host("other.example", "iosco_i_scan", parent_by_host, parent_descendants)
        self.assertEqual(child[0]["host_relation"], "CRIMSON_SUBDOMAIN_OF_REFERENCE_HOST")
        self.assertEqual(parent[0]["host_relation"], "REFERENCE_SUBDOMAIN_OF_CRIMSON_HOST")

    def test_cross_source_match_has_highest_review_reason(self):
        matches = [
            {"match_source_id": "iosco_i_scan", "host_relation": "EXACT_HOST"},
            {"match_source_id": "sec_iapd", "host_relation": "EXACT_HOST"},
        ]
        self.assertEqual(queue_reason(matches), "IOSCO_AND_SEC_REFERENCE")

    def test_end_to_end_outputs_create_no_labels(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            crimson = root / "crimson.jsonl"
            iosco = root / "iosco.jsonl"
            sec = root / "sec.jsonl"
            matches = root / "matches.jsonl"
            queue = root / "queue.jsonl"
            write_jsonl(crimson, [
                {"artifact_id": "C1", "source_id": "crimson_www_2025", "domain": "login.example.com"},
                {"artifact_id": "C2", "source_id": "crimson_www_2025", "domain": "unmatched.invalid"},
            ])
            write_jsonl(iosco, [{
                "source_id": "iosco_i_scan", "source_record_id": "I1",
                "observed_hosts": ["example.com"], "reference_role": "warning",
                "reference_semantics": "warning only",
            }])
            write_jsonl(sec, [{
                "source_id": "sec_iapd", "source_record_id": "S1",
                "observed_hosts": ["login.example.com"], "reference_role": "registration",
                "reference_semantics": "registration only",
            }])
            report = build_match_outputs(
                crimson, iosco, sec, matches, queue,
                input_hashes={"crimson": "a" * 64, "iosco": "b" * 64, "sec": "c" * 64},
            )
            match_records = [json.loads(line) for line in matches.read_text(encoding="utf-8").splitlines()]
            queue_record = json.loads(queue.read_text(encoding="utf-8").strip())
        self.assertEqual(report["coverage"]["crimson_record_count"], 2)
        self.assertEqual(report["coverage"]["crimson_records_with_reference_match"], 1)
        self.assertEqual(len(match_records), 2)
        self.assertEqual(queue_record["queue_reason"], "IOSCO_AND_SEC_REFERENCE")
        self.assertFalse(queue_record["label_created"])
        self.assertFalse(queue_record["identity_resolved"])
        self.assertEqual(report["safety_contract"]["labels_created"], 0)

    def test_frozen_registry_keeps_matching_non_decisional(self):
        path = ROOT / "registry" / "analyses" / "crimson_external_reference_match_v1.json"
        registry = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(registry["coverage"]["reference_match_pair_count"], 370)
        self.assertEqual(registry["coverage"]["unique_crimson_match_hosts_with_reference_match"], 344)
        self.assertFalse(registry["safety_contract"]["training_allowed"])
        self.assertFalse(registry["safety_contract"]["domain_access_allowed"])
        self.assertFalse(registry["safety_contract"]["automatic_entity_resolution_allowed"])
        self.assertFalse(registry["safety_contract"]["unmatched_means_safe"])


if __name__ == "__main__":
    unittest.main()
