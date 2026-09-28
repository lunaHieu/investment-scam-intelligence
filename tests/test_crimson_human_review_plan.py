import unittest

from scripts.prepare_crimson_human_review_plan import build_plan_records


def record(rank, source="iosco_i_scan", identity="SAME_ENTITY", second=False, live_gap=False):
    base = {
        "pilot_id": f"PILOT_{rank:03d}",
        "pilot_rank": rank,
        "crimson_host": f"host-{rank}.example",
        "reference_source": source,
        "identity_relationship": identity,
        "evidence_assessment": "WARNING_RELEVANT" if source == "iosco_i_scan" else "REGISTRATION_RELEVANT",
        "review_status": "IN_PROGRESS",
        "second_review_status": "REQUESTED" if second else "NOT_REQUESTED",
        "manual_live_url_followup_required": live_gap,
        "training_eligible": "NO",
        "label_created": False,
    }
    if source == "iosco_i_scan":
        base.update({
            "reference_record_ids": [str(rank)],
            "reference_details": [{"official_reference_url": f"https://regulator.example/{rank}"}],
            "live_reference_status": "PARTIAL_URLS_LIVE_CONFIRMED" if live_gap else "ALL_URLS_LIVE_CONFIRMED",
        })
    else:
        base.update({
            "reference_record_id": str(rank),
            "official_reference_url": f"https://adviserinfo.sec.gov/firm/summary/{rank}",
        })
    return base


class CrimsonHumanReviewPlanTests(unittest.TestCase):
    def test_priority_order_covers_every_review_path(self):
        rows = build_plan_records(
            [record(5, source="sec_iapd")],
            [
                record(1, identity="IMPERSONATION_SUSPECTED", second=True, live_gap=True),
                record(2, second=True, live_gap=True),
                record(3, second=True),
                record(4, live_gap=True),
            ],
        )
        self.assertEqual([row["pilot_rank"] for row in rows], [1, 2, 3, 4, 5])
        self.assertEqual([row["review_order"] for row in rows], [1, 2, 3, 4, 5])
        self.assertTrue(rows[0]["second_review_required"])
        self.assertEqual(rows[-1]["live_reference_status"], "OFFICIAL_PROFILE_SNAPSHOT")

    def test_plan_never_creates_labels_or_training_eligibility(self):
        rows = build_plan_records([record(1, source="sec_iapd")], [])
        self.assertEqual(rows[0]["review_status"], "IN_PROGRESS")
        self.assertEqual(rows[0]["adjudication_status"], "NOT_READY")
        self.assertEqual(rows[0]["training_eligible"], "NO")
        self.assertFalse(rows[0]["label_created"])
        self.assertTrue(rows[0]["do_not_open_crimson_host"])

    def test_rejects_labeled_or_duplicate_inputs(self):
        bad = record(1, source="sec_iapd")
        bad["label_created"] = True
        with self.assertRaises(ValueError):
            build_plan_records([bad], [])
        duplicate = record(2)
        with self.assertRaises(ValueError):
            build_plan_records([], [duplicate, dict(duplicate)])


if __name__ == "__main__":
    unittest.main()
