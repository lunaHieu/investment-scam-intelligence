import json
import tempfile
import unittest
from pathlib import Path

from scripts.reconcile_sec_edgar_iapd_v11_supplemental_capture import reconcile
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


class SecEdgarIapdV11SupplementalReconciliationTests(unittest.TestCase):
    def test_reconciliation_is_offline_and_preserves_reservation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = root / "raw.html"
            raw.write_bytes(b"<html>captured fixture</html>")
            plan = root / "plan.json"
            plan.write_text(json.dumps({"results": [{
                "availability_plan_id": "ID-1",
                "shortlist_id": "SL-1",
                "cohort": "EXTERNAL_HOLDOUT",
                "candidate_host": "example.test",
                "snapshot_timestamp": "20260101000000",
                "requested_archive_url": "https://web.archive.org/web/20260101000000id_/https://example.test/",
                "capture_path": str(raw),
            }]}), encoding="utf-8")
            release = root / "release.json"
            release.write_text(json.dumps({"inputs": {"capture_plan": {"path": str(plan), "sha256": sha256_file(plan)}}}), encoding="utf-8")
            release_qa = root / "release_qa.json"
            release_qa.write_text("{}", encoding="utf-8")
            reservation = root / "capture_report.json"
            reservation.write_text(json.dumps({
                "status": "RESERVED_BEFORE_NETWORK_NON_RESUMABLE",
                "release_sha256": sha256_file(release),
                "release_qa_sha256": sha256_file(release_qa),
                "planned_capture_count": 1,
            }), encoding="utf-8")
            output = root / "raw_reconciliation.json"
            result = reconcile(release, release_qa, reservation, output)
            self.assertEqual(result["status"], "PASS_RAW_BYTES_IDENTITY_RECONCILIATION_CAPTURE_METADATA_INCOMPLETE")
            self.assertEqual(json.loads(reservation.read_text(encoding="utf-8"))["status"], "RESERVED_BEFORE_NETWORK_NON_RESUMABLE")
            self.assertEqual(result["rows"][0]["sha256"], sha256_file(raw))
            self.assertFalse(result["decision"]["text_extraction_release_may_be_prepared"])


if __name__ == "__main__":
    unittest.main()
