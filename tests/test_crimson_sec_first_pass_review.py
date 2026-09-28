import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "prepare_crimson_sec_first_pass_review.py"
SPEC = importlib.util.spec_from_file_location("prepare_crimson_sec_first_pass_review", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class CrimsonSecFirstPassReviewTests(unittest.TestCase):
    def test_host_relationship(self):
        self.assertTrue(MODULE.host_is_same_or_subdomain("example.com", "example.com"))
        self.assertTrue(MODULE.host_is_same_or_subdomain("learn.example.com", "example.com"))
        self.assertFalse(MODULE.host_is_same_or_subdomain("fakeexample.com", "example.com"))

    def test_prepare_records_keeps_review_non_label(self):
        pilot = [
            {
                "pilot_id": f"P{i}",
                "pilot_rank": i,
                "reference_sources": ["sec_iapd"],
                "crimson_match_host": f"sub{i}.example{i}.com" if i > 6 else f"example{i}.com",
            }
            for i in range(1, 9)
        ]
        evidence = [
            {
                "pilot_id": f"P{i}",
                "match_source_id": "sec_iapd",
                "reference_record_id": str(i),
                "matched_reference_host": f"example{i}.com",
                "host_relation": "CRIMSON_SUBDOMAIN_OF_REFERENCE_HOST" if i > 6 else "EXACT_HOST",
            }
            for i in range(1, 9)
        ]
        sec = [
            {
                "source_record_id": str(i),
                "sec_number": f"801-{i}",
                "entity_name_keys": [f"entity {i}"],
                "observed_hosts": [f"example{i}.com"],
                "registration": {"firm_type": "Registered", "status": "APPROVED", "date": "2024-01-01"},
                "filing": {"date": "2026-01-01"},
                "source_version": "test",
                "source_raw_sha256": "a" * 64,
            }
            for i in range(1, 9)
        ]

        result = MODULE.prepare_records(pilot, evidence, sec)

        self.assertEqual(len(result), 8)
        self.assertTrue(all(row["review_status"] == "IN_PROGRESS" for row in result))
        self.assertTrue(all(row["identity_relationship"] == "SAME_ENTITY" for row in result))
        self.assertTrue(all(row["training_eligible"] == "NO" for row in result))
        self.assertTrue(all(row["label_created"] is False for row in result))
        self.assertTrue(all(row["human_confirmation_required"] is True for row in result))


if __name__ == "__main__":
    unittest.main()
