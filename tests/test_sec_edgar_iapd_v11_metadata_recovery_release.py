import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_sec_edgar_iapd_v11_metadata_recovery_release import build_plan, build_release, EXPECTED_IDS, PLAN_QA_STATUS
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


class V11MetadataRecoveryReleaseTests(unittest.TestCase):
    def test_plan_preserves_exact_two_rows_with_new_output_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.json"
            rows = [{"availability_plan_id": ident, "candidate_host": f"host{index}.test", "cohort": "EXTERNAL_HOLDOUT", "capture_path": str(root / "old" / f"{ident}.html")} for index, ident in enumerate(EXPECTED_IDS)]
            source.write_text(json.dumps({"results": rows}), encoding="utf-8")
            plan = build_plan(source, sha256_file(source), root / "new_raw")
            self.assertEqual(plan["ordered_ids"], list(EXPECTED_IDS))
            self.assertTrue(all("new_raw" in row["capture_path"] for row in plan["results"]))

    def test_release_requires_pinned_plan_qa_and_cooldown(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan = root / "plan.json"
            plan.write_text(json.dumps({"report_id": "ISI_SEC_EDGAR_IAPD_V11_METADATA_RECOVERY_PLAN_V1", "ordered_ids": list(EXPECTED_IDS), "planned_capture_count": 2}), encoding="utf-8")
            plan_qa = root / "plan_qa.json"
            plan_qa.write_text(json.dumps({"status": PLAN_QA_STATUS, "plan_sha256": sha256_file(plan)}), encoding="utf-8")
            availability = root / "availability.json"
            availability.write_text(json.dumps({"status": "COMPLETE", "created_at": "2026-10-25T05:39:42.463320+07:00"}), encoding="utf-8")
            availability_qa = root / "availability_qa.json"
            availability_qa.write_text(json.dumps({"inputs": {"report_sha256": sha256_file(availability)}}), encoding="utf-8")
            reservation = root / "reservation.json"
            reservation.write_text(json.dumps({"status": "RESERVED_BEFORE_NETWORK_NON_RESUMABLE"}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "plan|timestamp|cooldown"):
                build_release(plan, plan_qa, availability, availability_qa, reservation, "2026-10-26T00:00:00+07:00", "2026-10-26T05:39:42+07:00", root / "report.json")


if __name__ == "__main__":
    unittest.main()
