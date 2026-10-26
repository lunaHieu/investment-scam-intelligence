import json
import tempfile
import unittest
from pathlib import Path

from scripts.repair_sec_edgar_iapd_v11_supplemental_capture_result import build_repair
from scripts.verify_sec_edgar_iapd_v11_supplemental_capture_repaired_result import verify
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


class SecEdgarIapdV11SupplementalRepairedResultTests(unittest.TestCase):
    def test_repair_and_independent_verification_keep_metadata_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = root / "raw.html"
            raw.write_bytes(b"<html>captured fixture</html>")
            plan = root / "plan.json"
            plan.write_text(json.dumps({"results": [{
                "availability_plan_id": "ID-1", "shortlist_id": "SL-1", "cohort": "EXTERNAL_HOLDOUT",
                "candidate_host": "example.test", "candidate_url": "https://example.test/",
                "snapshot_timestamp": "20260101000000", "snapshot_url": "https://web.archive.org/web/20260101000000/https://example.test/",
                "requested_archive_url": "https://web.archive.org/web/20260101000000id_/https://example.test/",
                "capture_path": str(raw),
            }]}), encoding="utf-8")
            release = root / "release.json"
            release.write_text(json.dumps({"inputs": {"capture_plan": {"path": str(plan), "sha256": sha256_file(plan)},}, "planned_output": {"report_id": "ORIGINAL"}}), encoding="utf-8")
            release_qa = root / "release_qa.json"
            release_qa.write_text("{}", encoding="utf-8")
            reservation = root / "reservation.json"
            reservation.write_text(json.dumps({"status": "RESERVED_BEFORE_NETWORK_NON_RESUMABLE"}), encoding="utf-8")
            reconciliation = root / "reconciliation.json"
            reconciliation.write_text(json.dumps({
                "status": "PASS_RAW_BYTES_IDENTITY_RECONCILIATION_CAPTURE_METADATA_INCOMPLETE",
                "decision": {"capture_result_qa_passed": False},
                "inputs": {"release_sha256": sha256_file(release), "release_qa_sha256": sha256_file(release_qa)},
                "rows": [{"availability_plan_id": "ID-1", "shortlist_id": "SL-1", "cohort": "EXTERNAL_HOLDOUT", "candidate_host": "example.test", "snapshot_timestamp": "20260101000000", "requested_archive_url": "https://web.archive.org/web/20260101000000id_/https://example.test/", "capture_path": str(raw), "bytes": raw.stat().st_size, "sha256": sha256_file(raw)}],
            }), encoding="utf-8")
            repaired = root / "repaired.json"
            build_repair(release, release_qa, reservation, reconciliation, repaired)
            qa = verify(release, repaired)
            self.assertEqual(qa["status"], "PASS_REPAIRED_RAW_BYTES_METADATA_INCOMPLETE_EXTRACTION_CLOSED")
            self.assertFalse(qa["decision"]["text_extraction_release_may_be_prepared"])


if __name__ == "__main__":
    unittest.main()
