import json
import unittest
from pathlib import Path

from src.isi.curation.external_text_capture_queue import (
    select_capture_candidates,
    select_confirmed_reserve_candidates,
    select_legitimate_reserve_candidates,
)


ROOT = Path(__file__).resolve().parents[1]


def iosco_record(record_id, host, jurisdiction="Australia", *, notice_host="regulator.example"):
    return {
        "source_id": "iosco_i_scan",
        "source_record_id": str(record_id),
        "entity_name_keys": [f"warning entity {record_id}"],
        "observed_hosts": [host],
        "quality_flags": [],
        "reference_role": "REGULATOR_WARNING_EVIDENCE",
        "notice_reference_url": f"https://{notice_host}/warning/{record_id}",
        "regulator": {"name": "Regulator", "jurisdiction": jurisdiction},
        "evidence_dates": {"validation_date": "2026-09-21"},
        "warning_categories": {"detail": "Unregistered entity"},
    }


def sec_record(
    record_id,
    host,
    *,
    status="APPROVED",
    firm_type="Registered",
    entity_name=None,
    registration_date="2020-01-02",
    filing_date="2026-03-04",
):
    return {
        "source_id": "sec_iapd",
        "source_record_id": str(record_id),
        "entity_name_keys": [entity_name or f"registered firm {record_id}"],
        "observed_hosts": [host],
        "quality_flags": [],
        "reference_role": "REGISTERED_OR_EXEMPT_REPORTING_ENTITY_REFERENCE",
        "sec_number": f"801-{record_id}",
        "registration": {
            "date": registration_date,
            "firm_type": firm_type,
            "status": status,
        },
        "filing": {"date": filing_date},
    }


class ExternalTextCaptureQueueTests(unittest.TestCase):
    def test_queue_is_balanced_deterministic_and_unlabeled(self):
        iosco = [iosco_record(i, f"warn-{i}.example", f"J{i % 3}") for i in range(1, 9)]
        sec = [sec_record(i, f"legit-{i}.example") for i in range(1, 9)]
        first = select_capture_candidates(iosco, sec, per_target=5, seed="test")
        second = select_capture_candidates(iosco, sec, per_target=5, seed="test")
        self.assertEqual(first, second)
        queue, report = first
        self.assertEqual(report["selected_counts"]["total"], 10)
        self.assertEqual(
            {item["target_outcome"] for item in queue},
            {"CONFIRMED_CANDIDATE", "LEGITIMATE_CANDIDATE"},
        )
        self.assertTrue(all(item["review_state"]["ground_truth_status"] == "UNCERTAIN" for item in queue))
        self.assertTrue(all(item["training_eligible"] == "NO" for item in queue))
        self.assertTrue(all(item["label_created"] is False for item in queue))
        self.assertFalse(report["safety_contract"]["training_allowed"])

    def test_filters_shared_platform_collision_and_nonapproved_registration(self):
        iosco = [
            iosco_record(1, "collision.example"),
            iosco_record(2, "warn-clean.example"),
        ]
        sec = [
            sec_record(1, "collision.example"),
            sec_record(2, "facebook.com"),
            sec_record(3, "inactive.example", status="REVOKED"),
            sec_record(4, "legit-clean.example"),
        ]
        queue, report = select_capture_candidates(iosco, sec, per_target=1, seed="test")
        legitimate = [item for item in queue if item["target_outcome"] == "LEGITIMATE_CANDIDATE"]
        self.assertEqual(legitimate[0]["candidate_host"], "legit-clean.example")
        self.assertEqual(report["exclusion_counts"]["sec_iosco_host_collision"], 1)
        self.assertEqual(report["exclusion_counts"]["sec_not_single_clean_host"], 1)
        self.assertEqual(report["exclusion_counts"]["sec_not_registered_approved"], 1)

    def test_warning_notice_must_not_be_the_candidate_host(self):
        iosco = [
            iosco_record(1, "unsafe.example", notice_host="unsafe.example"),
            iosco_record(2, "clean.example"),
        ]
        sec = [sec_record(1, "legit.example")]
        queue, report = select_capture_candidates(iosco, sec, per_target=1)
        warning = [item for item in queue if item["target_outcome"] == "CONFIRMED_CANDIDATE"]
        self.assertEqual(warning[0]["candidate_host"], "clean.example")
        self.assertEqual(report["exclusion_counts"]["iosco_notice_is_candidate_host"], 1)

    def test_checked_in_registry_keeps_queue_unlabeled_and_balanced(self):
        registry = json.loads(
            (ROOT / "registry" / "pilots" / "external_text_capture_candidate_queue_v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(registry["coverage"]["candidate_count"], 30)
        self.assertEqual(registry["coverage"]["confirmed_candidate_count"], 15)
        self.assertEqual(registry["coverage"]["legitimate_candidate_count"], 15)
        self.assertEqual(registry["coverage"]["external_evaluation_eligible_count"], 0)
        self.assertEqual(registry["coverage"]["labels_created"], 0)
        self.assertFalse(registry["next_gate"]["model_scoring_allowed"])
        self.assertFalse(registry["safety_contract"]["training_allowed"])

    def test_reserve_queue_filters_risky_or_weak_candidates(self):
        iosco = [iosco_record(1, "warning-collision.example")]
        sec = [
            sec_record(1, "existing.example", entity_name="Existing"),
            sec_record(2, "warning-collision.example", entity_name="Warning Collision"),
            sec_record(3, "shared.example", entity_name="Shared One"),
            sec_record(4, "shared.example", entity_name="Shared Two"),
            sec_record(
                5,
                "newfirm.example",
                entity_name="New Firm",
                registration_date="2025-01-01",
            ),
            sec_record(
                6,
                "stale.example",
                entity_name="Stale",
                filing_date="2024-12-31",
            ),
            sec_record(7, "unrelated.example", entity_name="Completely Different Name"),
            sec_record(8, "alpharidge.example", entity_name="Alpha Ridge Capital"),
            sec_record(9, "betaharbor.example", entity_name="Beta Harbor Advisors"),
        ]

        queue, report = select_legitimate_reserve_candidates(
            iosco,
            sec,
            {"existing.example"},
            reserve_size=2,
            seed="test",
        )

        self.assertEqual([item["candidate_host"] for item in queue], [
            "alpharidge.example",
            "betaharbor.example",
        ])
        self.assertEqual(report["selected_count"], 2)
        self.assertEqual(report["exclusion_counts"]["already_in_primary_queue"], 1)
        self.assertEqual(report["exclusion_counts"]["iosco_host_collision"], 1)
        self.assertEqual(report["exclusion_counts"]["shared_sec_host"], 2)
        self.assertEqual(report["exclusion_counts"]["insufficient_registration_tenure"], 1)
        self.assertEqual(report["exclusion_counts"]["filing_not_recent"], 1)
        self.assertEqual(report["exclusion_counts"]["low_domain_identity_affinity"], 1)
        self.assertTrue(all(item["review_state"]["ground_truth_status"] == "UNCERTAIN" for item in queue))
        self.assertTrue(all(item["training_eligible"] == "NO" for item in queue))
        self.assertTrue(all(item["label_created"] is False for item in queue))
        self.assertFalse(report["safety_contract"]["training_allowed"])

    def test_reserve_queue_is_deterministic_and_excludes_primary_hosts(self):
        sec = [
            sec_record(i, f"firm{i}.example", entity_name=f"Firm {i}")
            for i in range(1, 6)
        ]
        first = select_legitimate_reserve_candidates(
            [], sec, {"firm1.example"}, reserve_size=3, seed="fixed"
        )
        second = select_legitimate_reserve_candidates(
            [], sec, {"firm1.example"}, reserve_size=3, seed="fixed"
        )
        self.assertEqual(first, second)
        self.assertNotIn("firm1.example", {item["candidate_host"] for item in first[0]})

    def test_confirmed_reserve_prefers_recent_high_affinity_unique_hosts(self):
        iosco = [
            {**iosco_record(1, "existing.example"), "entity_name_keys": ["Existing"]},
            {**iosco_record(2, "alpha-advisory.example"), "entity_name_keys": ["Alpha Advisory"]},
            {**iosco_record(3, "beta-capital.example"), "entity_name_keys": ["Beta Capital"]},
            {**iosco_record(4, "unrelated.example"), "entity_name_keys": ["Different Name"]},
        ]
        queue, report = select_confirmed_reserve_candidates(
            iosco,
            {"existing.example"},
            reserve_size=2,
            seed="fixed",
            candidate_id_prefix="EXTCAP_RESERVE2_CONF",
        )
        self.assertEqual(
            {item["candidate_host"] for item in queue},
            {"alpha-advisory.example", "beta-capital.example"},
        )
        self.assertTrue(all(item["target_outcome"] == "CONFIRMED_RESERVE_CANDIDATE" for item in queue))
        self.assertTrue(all(item["candidate_id"].startswith("EXTCAP_RESERVE2_CONF_") for item in queue))
        self.assertTrue(all(item["review_state"]["ground_truth_status"] == "UNCERTAIN" for item in queue))
        self.assertTrue(all(item["label_created"] is False for item in queue))
        self.assertEqual(report["exclusion_counts"]["already_in_primary_queue"], 1)
        self.assertEqual(report["exclusion_counts"]["low_domain_identity_affinity"], 1)
        self.assertFalse(report["safety_contract"]["training_allowed"])

    def test_checked_in_reserve_registry_keeps_all_gates_closed(self):
        registry = json.loads(
            (ROOT / "registry" / "pilots" / "sec_legitimate_capture_reserve_v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(registry["coverage"]["reserve_candidate_count"], 30)
        self.assertEqual(registry["coverage"]["external_evaluation_eligible_count"], 0)
        self.assertEqual(registry["coverage"]["labels_created"], 0)
        self.assertFalse(registry["next_gate"]["model_scoring_allowed"])
        self.assertFalse(registry["safety_contract"]["training_allowed"])

    def test_checked_in_confirmed_reserve_registry_keeps_all_gates_closed(self):
        registry = json.loads(
            (ROOT / "registry" / "pilots" / "iosco_confirmed_capture_reserve_v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(registry["coverage"]["reserve_candidate_count"], 40)
        self.assertEqual(registry["coverage"]["external_evaluation_eligible_count"], 0)
        self.assertEqual(registry["coverage"]["labels_created"], 0)
        self.assertFalse(registry["next_gate"]["model_scoring_allowed"])
        self.assertFalse(registry["safety_contract"]["training_allowed"])

        registry_v2 = json.loads(
            (ROOT / "registry" / "pilots" / "iosco_confirmed_capture_reserve_v2.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(registry_v2["coverage"]["reserve_candidate_count"], 100)
        self.assertEqual(registry_v2["coverage"]["external_evaluation_eligible_count"], 0)
        self.assertFalse(registry_v2["next_gate"]["model_scoring_allowed"])
        self.assertFalse(registry_v2["safety_contract"]["training_allowed"])

    def test_reserve_capture_registry_preserves_human_review_gate(self):
        registry = json.loads(
            (
                ROOT
                / "registry"
                / "pilots"
                / "external_text_legitimate_reserve_capture_v1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(registry["acquisition"]["successful_capture_count"], 9)
        self.assertEqual(registry["readiness"]["combined_legitimate_captured_record_count"], 11)
        self.assertEqual(registry["readiness"]["human_reconciled_count"], 0)
        self.assertEqual(registry["readiness"]["eligible_legitimate_count"], 0)
        self.assertFalse(registry["decision"]["promote_to_legitimate_label"])
        self.assertFalse(registry["decision"]["open_external_scoring"])
        self.assertFalse(registry["safety_contract"]["training_allowed"])

    def test_resolver_pinned_capture_script_does_not_auto_follow_redirects(self):
        script = (ROOT / "scripts" / "capture_sec_reserve_homepages_v2.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("--resolve", script)
        self.assertIn("Redirect guard rejected URL", script)
        self.assertNotIn("'--location'", script)
        self.assertIn("$redirectUri.Scheme -ne 'https'", script)


if __name__ == "__main__":
    unittest.main()
