import unittest
import json
from pathlib import Path

from src.isi.curation.crimson_reference_pilot import select_pilot


ROOT = Path(__file__).resolve().parents[1]


def queue_record(host, reason, rank, shared=False):
    source = "sec_iapd" if reason.startswith("SEC_") else "iosco_i_scan"
    return {
        "crimson_match_host": host,
        "queue_reason": reason,
        "queue_rank": rank,
        "match_count": 1,
        "shared_reference_host_present": shared,
        "observed_crimson_domains": [host],
        "crimson_artifact_ids": [f"A{rank}"],
        "reference_record_ids": {"iosco_i_scan": [str(rank)] if source == "iosco_i_scan" else [], "sec_iapd": [str(rank)] if source == "sec_iapd" else []},
        "interpretation": "review only",
        "label_created": False,
        "identity_resolved": False,
    }


def match_record(queue):
    source = "sec_iapd" if queue["queue_reason"].startswith("SEC_") else "iosco_i_scan"
    host = queue["crimson_match_host"]
    return {
        "crimson_match_host": host,
        "crimson_artifact_id": queue["crimson_artifact_ids"][0],
        "crimson_domain": host,
        "match_source_id": source,
        "reference_record_id": str(queue["queue_rank"]),
        "reference_role": "reference",
        "host_relation": "EXACT_HOST" if "EXACT" in queue["queue_reason"] else "CRIMSON_SUBDOMAIN_OF_REFERENCE_HOST",
        "matched_reference_host": host,
        "reference_host_record_count": 2 if queue["shared_reference_host_present"] else 1,
        "notice_reference_url": "https://regulator.example/notice" if source == "iosco_i_scan" else None,
        "sec_number": "801-1" if source == "sec_iapd" else None,
        "label_created": False,
        "identity_resolved": False,
    }


class CrimsonReferenceReviewPilotTests(unittest.TestCase):
    def test_selection_includes_all_sec_and_is_deterministic(self):
        queue = [
            queue_record("sec-exact.example", "SEC_EXACT_HOST", 1),
            queue_record("sec-hierarchy.example", "SEC_HOST_HIERARCHY", 2),
            queue_record("shared-1.example", "IOSCO_EXACT_HOST", 3, True),
            queue_record("shared-2.example", "IOSCO_EXACT_HOST", 4, True),
            queue_record("child-1.example", "IOSCO_HOST_HIERARCHY", 5),
            queue_record("child-2.example", "IOSCO_HOST_HIERARCHY", 6),
            queue_record("fill-1.example", "IOSCO_EXACT_HOST", 7),
            queue_record("fill-2.example", "IOSCO_EXACT_HOST", 8),
        ]
        matches = [match_record(record) for record in queue]
        first = select_pilot(queue, matches, pilot_size=7, ambiguous_exact_quota=1, hierarchy_quota=2)
        second = select_pilot(queue, matches, pilot_size=7, ambiguous_exact_quota=1, hierarchy_quota=2)
        self.assertEqual(first, second)
        selected_hosts = {record["crimson_match_host"] for record in first[0]}
        self.assertIn("sec-exact.example", selected_hosts)
        self.assertIn("sec-hierarchy.example", selected_hosts)
        self.assertEqual(first[2]["pilot_record_count"], 7)

    def test_pilot_stays_unreviewed_and_not_training_eligible(self):
        queue = [queue_record("sec.example", "SEC_EXACT_HOST", 1)]
        pilot, evidence, report = select_pilot(
            queue, [match_record(queue[0])], pilot_size=1, ambiguous_exact_quota=0, hierarchy_quota=0
        )
        self.assertEqual(pilot[0]["review_status"], "NOT_STARTED")
        self.assertEqual(pilot[0]["training_eligible"], "NO")
        self.assertFalse(pilot[0]["label_created"])
        self.assertFalse(evidence[0]["identity_resolved"])
        self.assertFalse(report["safety_contract"]["training_allowed"])

    def test_checked_in_pilot_registry_freezes_unreviewed_scope(self):
        path = ROOT / "registry" / "pilots" / "crimson_external_reference_review_pilot_v1.json"
        registry = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(registry["coverage"]["pilot_record_count"], 40)
        self.assertEqual(registry["selection_protocol"]["strata"]["ALL_SEC_MATCHES"], 8)
        self.assertEqual(registry["coverage"]["training_eligible_count"], 0)
        self.assertFalse(registry["safety_contract"]["training_allowed"])
        self.assertFalse(registry["safety_contract"]["domain_access_allowed"])


if __name__ == "__main__":
    unittest.main()
